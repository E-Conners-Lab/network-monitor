"""Config backup Celery tasks."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from netmiko import ConnectHandler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.models.config_backup import ConfigBackup
from src.models.device import Device
from src.tasks import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Singleton engine and session factory
_async_engine = None
_async_session_factory = None


def get_async_engine():
    """Get singleton async database engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _async_engine


def get_async_session():
    """Get singleton async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


async def save_config_backup(
    db: AsyncSession,
    device_id: int,
    config_text: str,
    config_type: str,
    triggered_by: str,
) -> ConfigBackup:
    """Save a config backup to the database."""
    config_hash = ConfigBackup.compute_hash(config_text)
    config_size = len(config_text.encode())
    line_count = config_text.count("\n") + 1

    # Check if this exact config already exists (by hash)
    existing = await db.execute(
        select(ConfigBackup).where(
            ConfigBackup.device_id == device_id,
            ConfigBackup.config_hash == config_hash,
        ).limit(1)
    )

    if existing.scalar_one_or_none():
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
    await db.commit()
    await db.refresh(backup)

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

    async def _backup():
        session_factory = get_async_session()
        async with session_factory() as db:
            # Get devices
            result = await db.execute(
                select(Device).where(
                    Device.id.in_(device_ids),
                    Device.is_active == True,  # noqa: E712
                    Device.is_reachable == True,  # noqa: E712
                )
            )
            devices = result.scalars().all()

            if not devices:
                logger.warning("No reachable devices found for backup")
                return {"success": 0, "failed": 0, "unchanged": 0}

            # Get SSH credentials from settings or tags
            username = settings.ssh_username
            password = settings.ssh_password

            # Collect configs in parallel using ThreadPoolExecutor
            results = {"success": 0, "failed": 0, "unchanged": 0}
            device_map = {d.name: d for d in devices}

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
                        # Save to database
                        backup = await save_config_backup(
                            db, device.id, config_text, config_type, triggered_by
                        )
                        if backup:
                            results["success"] += 1
                        else:
                            results["unchanged"] += 1

            return results

    result = run_async(_backup())
    logger.info(f"Config backup complete: {result}")
    return result


@celery_app.task(name="tasks.scheduled_config_backup")
def scheduled_config_backup():
    """Scheduled task to backup all active device configs."""
    logger.info("Running scheduled config backup")

    async def _get_device_ids():
        session_factory = get_async_session()
        async with session_factory() as db:
            result = await db.execute(
                select(Device.id).where(
                    Device.is_active == True,  # noqa: E712
                )
            )
            return [row[0] for row in result.fetchall()]

    device_ids = run_async(_get_device_ids())

    if device_ids:
        return backup_device_configs.delay(
            device_ids=device_ids,
            config_type="running",
            triggered_by="scheduled",
        )

    return {"message": "No active devices to backup"}
