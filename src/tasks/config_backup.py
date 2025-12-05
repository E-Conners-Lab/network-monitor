"""Config backup Celery tasks."""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from netmiko import ConnectHandler
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.models.config_backup import ConfigBackup
from src.models.device import Device
from src.tasks import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Sync database engine for Celery tasks
_sync_engine = None
_sync_session_factory = None


def get_sync_engine():
    """Get singleton sync database engine."""
    global _sync_engine
    if _sync_engine is None:
        # Convert async URL to sync (postgresql+asyncpg -> postgresql+psycopg2)
        sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
        _sync_engine = create_engine(
            sync_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _sync_engine


def get_sync_session():
    """Get singleton sync session factory."""
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(
            engine, class_=Session, expire_on_commit=False
        )
    return _sync_session_factory


def compute_config_hash(config_text: str) -> str:
    """Compute SHA-256 hash of config text."""
    return hashlib.sha256(config_text.encode()).hexdigest()


def collect_config_netmiko(
    device_name: str,
    ip_address: str,
    username: str,
    password: str,
    config_type: str = "running",
) -> tuple[str, str | None, str | None]:
    """
    Collect config from device using Netmiko.

    Returns: (device_name, config_text, error)
    """
    try:
        logger.info(f"Collecting {config_type} config from {device_name} ({ip_address})")

        conn = ConnectHandler(
            device_type="cisco_ios",
            host=ip_address,
            username=username,
            password=password,
            timeout=30,
            conn_timeout=15,
        )

        if config_type == "running":
            config = conn.send_command("show running-config", read_timeout=60)
        else:
            config = conn.send_command("show startup-config", read_timeout=60)

        conn.disconnect()

        logger.info(f"Successfully collected config from {device_name} ({len(config)} bytes)")
        return (device_name, config, None)

    except Exception as e:
        logger.error(f"Failed to collect config from {device_name}: {e}")
        return (device_name, None, str(e))


def save_config_backup(
    db: Session,
    device_id: int,
    config_text: str,
    config_type: str,
    triggered_by: str,
) -> ConfigBackup | None:
    """Save a config backup to the database."""
    config_hash = compute_config_hash(config_text)
    config_size = len(config_text.encode())
    line_count = config_text.count("\n") + 1

    # Check if this exact config already exists (by hash)
    existing = db.execute(
        select(ConfigBackup).where(
            and_(
                ConfigBackup.device_id == device_id,
                ConfigBackup.config_hash == config_hash,
            )
        ).limit(1)
    ).scalar_one_or_none()

    if existing:
        logger.info(f"Config unchanged for device {device_id} (hash: {config_hash[:8]}...)")
        return None

    backup = ConfigBackup(
        device_id=device_id,
        config_type=config_type,
        config_text=config_text,
        config_hash=config_hash,
        config_size=config_size,
        line_count=line_count,
        collection_method="netmiko",
        triggered_by=triggered_by,
    )

    db.add(backup)
    db.commit()
    db.refresh(backup)

    logger.info(f"Saved config backup {backup.id} for device {device_id}")
    return backup


@celery_app.task(bind=True, name="tasks.backup_device_configs")
def backup_device_configs(
    self,
    device_ids: list[int],
    config_type: str = "running",
    triggered_by: str = "scheduled",
):
    """
    Backup configs for specified devices.

    Uses Netmiko for collection with parallel execution.
    """
    logger.info(f"Starting config backup for {len(device_ids)} devices")

    session_factory = get_sync_session()

    with session_factory() as db:
        # Get devices
        result = db.execute(
            select(Device).where(
                and_(
                    Device.id.in_(device_ids),
                    Device.is_active == True,  # noqa: E712
                    Device.is_reachable == True,  # noqa: E712
                )
            )
        )
        devices = result.scalars().all()

        if not devices:
            logger.warning("No reachable devices found for backup")
            return {"success": 0, "failed": 0, "unchanged": 0}

        # Get SSH credentials from settings
        username = settings.ssh_username
        password = settings.ssh_password

        # Collect configs in parallel using ThreadPoolExecutor
        results = {"success": 0, "failed": 0, "unchanged": 0}
        collected_configs = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(
                    collect_config_netmiko,
                    device.name,
                    device.ip_address,
                    # Use device-specific creds from tags if available
                    device.tags.get("ssh_username", username) if device.tags else username,
                    device.tags.get("ssh_password", password) if device.tags else password,
                    config_type,
                ): device
                for device in devices
            }

            for future in as_completed(futures):
                device = futures[future]
                device_name, config_text, error = future.result()

                if error:
                    logger.error(f"Backup failed for {device_name}: {error}")
                    results["failed"] += 1
                elif config_text:
                    collected_configs.append((device.id, config_text))

        # Save configs to database (after ThreadPoolExecutor completes)
        for device_id, config_text in collected_configs:
            backup = save_config_backup(
                db, device_id, config_text, config_type, triggered_by
            )
            if backup:
                results["success"] += 1
            else:
                results["unchanged"] += 1

    logger.info(f"Config backup complete: {results}")
    return results


@celery_app.task(name="tasks.scheduled_config_backup")
def scheduled_config_backup():
    """Scheduled task to backup all active device configs."""
    logger.info("Running scheduled config backup")

    session_factory = get_sync_session()

    with session_factory() as db:
        result = db.execute(
            select(Device.id).where(
                Device.is_active == True,  # noqa: E712
            )
        )
        device_ids = [row[0] for row in result.fetchall()]

    if device_ids:
        return backup_device_configs.delay(
            device_ids=device_ids,
            config_type="running",
            triggered_by="scheduled",
        )

    return {"message": "No active devices to backup"}
