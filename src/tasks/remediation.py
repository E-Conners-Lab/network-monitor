"""Remediation tasks for automated fixes."""

import asyncio
import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.drivers import ConnectionParams, DevicePlatform, SSHDriver
from src.integrations.netbox import NetBoxClient
from src.models.alert import Alert, AlertStatus
from src.models.device import Device, DeviceType
from src.models.remediation_log import RemediationLog, RemediationStatus
from src.tasks import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def get_async_engine():
    """Get async database engine for Celery tasks."""
    return create_async_engine(settings.database_url, echo=settings.debug)


def get_async_session():
    """Get async session factory."""
    engine = get_async_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    """Run an async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_device_credentials(device: Device) -> dict:
    """Get device credentials from NetBox or return defaults from config."""
    credentials = {
        "username": None,
        "password": None,
        "enable_password": None,
    }

    # Try to get from NetBox
    if device.netbox_id:
        try:
            netbox_client = NetBoxClient()
            if netbox_client.is_configured:
                nb_creds = netbox_client.get_device_credentials(device.netbox_id)
                if nb_creds:
                    credentials.update(nb_creds)
        except Exception as e:
            logger.warning(f"Could not fetch credentials from NetBox: {e}")

    # Fall back to default SSH credentials from config if not found in NetBox
    if not credentials.get("username") and settings.ssh_username:
        credentials["username"] = settings.ssh_username
        credentials["password"] = settings.ssh_password
        credentials["enable_password"] = settings.ssh_password

    return credentials


def get_ssh_driver(device: Device, credentials: dict) -> SSHDriver | None:
    """Create an SSH driver for a device."""
    if not credentials.get("username") or not credentials.get("password"):
        logger.error(f"No credentials available for device {device.name}")
        return None

    platform_map = {
        DeviceType.ROUTER: DevicePlatform.CISCO_IOS,
        DeviceType.SWITCH: DevicePlatform.CISCO_IOS,
        DeviceType.FIREWALL: DevicePlatform.CISCO_ASA,
    }
    platform = platform_map.get(device.device_type, DevicePlatform.CISCO_IOS)

    params = ConnectionParams(
        host=device.ip_address,
        username=credentials["username"],
        password=credentials["password"],
        enable_password=credentials.get("enable_password"),
        port=device.ssh_port,
        timeout=settings.ssh_timeout_seconds,
        platform=platform,
    )

    return SSHDriver(params)


async def create_remediation_log(
    db: AsyncSession,
    device_id: int,
    playbook_name: str,
    action_type: str,
    alert_id: int | None = None,
) -> RemediationLog:
    """Create a remediation log entry."""
    log = RemediationLog(
        device_id=device_id,
        alert_id=alert_id,
        playbook_name=playbook_name,
        action_type=action_type,
        status=RemediationStatus.PENDING,
    )
    db.add(log)
    await db.flush()
    return log


@celery_app.task(bind=True)
def execute_remediation(self, device_id: int, playbook_name: str, alert_id: int = None):
    """Execute a remediation playbook on a device."""
    logger.info(f"Starting remediation: playbook={playbook_name}, device={device_id}")

    async def _execute():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                # Get device
                result = await db.execute(
                    select(Device).where(Device.id == device_id)
                )
                device = result.scalar_one_or_none()

                if not device:
                    return {"status": "error", "error": f"Device {device_id} not found"}

                # Create remediation log
                log = await create_remediation_log(
                    db, device_id, playbook_name, "execute_playbook", alert_id
                )
                log.status = RemediationStatus.IN_PROGRESS
                log.started_at = datetime.utcnow()
                await db.flush()

                # Get credentials
                credentials = get_device_credentials(device)
                if not credentials.get("username"):
                    log.status = RemediationStatus.FAILED
                    log.error_message = "No credentials available for device"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {
                        "status": "error",
                        "error": "No credentials available",
                        "remediation_id": log.id,
                    }

                # Get SSH driver
                driver = get_ssh_driver(device, credentials)
                if not driver:
                    log.status = RemediationStatus.FAILED
                    log.error_message = "Could not create SSH driver"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {
                        "status": "error",
                        "error": "Could not create SSH driver",
                        "remediation_id": log.id,
                    }

                try:
                    # Connect to device
                    connect_result = driver.connect()
                    if not connect_result.success:
                        raise Exception(f"Connection failed: {connect_result.error}")

                    # Capture state before
                    version_result = driver.get_version()
                    interfaces_before = driver.get_interfaces()
                    log.state_before = {
                        "version": version_result.data[:500] if version_result.data else None,
                        "interfaces": interfaces_before.data if interfaces_before.success else None,
                    }

                    # Execute playbook commands based on playbook name
                    playbook_commands = get_playbook_commands(playbook_name, device)
                    log.commands_executed = playbook_commands

                    if playbook_commands:
                        config_result = driver.configure(playbook_commands)
                        log.command_output = config_result.raw_output

                        if not config_result.success:
                            raise Exception(f"Configuration failed: {config_result.error}")

                    # Capture state after
                    interfaces_after = driver.get_interfaces()
                    log.state_after = {
                        "interfaces": interfaces_after.data if interfaces_after.success else None,
                    }

                    driver.disconnect()

                    # Update log as successful
                    log.status = RemediationStatus.SUCCESS
                    log.completed_at = datetime.utcnow()
                    log.duration_ms = int(
                        (log.completed_at - log.started_at).total_seconds() * 1000
                    )

                    # Update alert if applicable
                    if alert_id:
                        alert_result = await db.execute(
                            select(Alert).where(Alert.id == alert_id)
                        )
                        alert = alert_result.scalar_one_or_none()
                        if alert:
                            alert.status = AlertStatus.RESOLVED
                            alert.resolved_at = datetime.utcnow()
                            alert.resolution_notes = f"Auto-remediated by playbook: {playbook_name}"

                    await db.commit()

                    return {
                        "status": "success",
                        "device_id": device_id,
                        "playbook": playbook_name,
                        "remediation_id": log.id,
                        "commands_executed": len(playbook_commands),
                    }

                except Exception as e:
                    logger.error(f"Remediation failed for {device.name}: {e}")
                    log.status = RemediationStatus.FAILED
                    log.error_message = str(e)
                    log.completed_at = datetime.utcnow()
                    await db.commit()

                    if driver.is_connected:
                        driver.disconnect()

                    return {
                        "status": "error",
                        "device_id": device_id,
                        "playbook": playbook_name,
                        "error": str(e),
                        "remediation_id": log.id,
                    }

            except Exception as e:
                logger.error(f"execute_remediation failed: {e}")
                return {"status": "error", "error": str(e)}

    return run_async(_execute())


def get_playbook_commands(playbook_name: str, device: Device) -> list[str]:
    """Get commands for a playbook based on device type."""
    playbooks = {
        "clear_arp_cache": ["clear arp-cache"],
        "clear_ip_route_cache": ["clear ip route *"],
        "save_config": ["write memory"],
        "reload_device": ["reload in 1"],
    }

    # ASA-specific playbooks
    asa_playbooks = {
        "clear_conn": ["clear conn all"],
        "clear_xlate": ["clear xlate"],
    }

    if device.device_type == DeviceType.FIREWALL:
        playbooks.update(asa_playbooks)

    return playbooks.get(playbook_name, [])


@celery_app.task(bind=True)
def interface_enable(self, device_id: int, interface_name: str):
    """Enable a disabled interface."""
    logger.info(f"Enabling interface {interface_name} on device {device_id}")

    async def _enable():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                # Get device
                result = await db.execute(
                    select(Device).where(Device.id == device_id)
                )
                device = result.scalar_one_or_none()

                if not device:
                    return {"status": "error", "error": f"Device {device_id} not found"}

                # Create remediation log
                log = await create_remediation_log(
                    db, device_id, "interface_enable", "interface_enable"
                )
                log.status = RemediationStatus.IN_PROGRESS
                log.started_at = datetime.utcnow()
                await db.flush()

                # Get credentials
                credentials = get_device_credentials(device)
                if not credentials.get("username"):
                    log.status = RemediationStatus.FAILED
                    log.error_message = "No credentials available"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {"status": "error", "error": "No credentials available"}

                driver = get_ssh_driver(device, credentials)
                if not driver:
                    log.status = RemediationStatus.FAILED
                    log.error_message = "Could not create SSH driver"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {"status": "error", "error": "Could not create driver"}

                try:
                    connect_result = driver.connect()
                    if not connect_result.success:
                        raise Exception(f"Connection failed: {connect_result.error}")

                    # Enable interface
                    enable_result = driver.enable_interface(interface_name)
                    log.commands_executed = [
                        f"interface {interface_name}",
                        "no shutdown",
                    ]
                    log.command_output = enable_result.raw_output

                    if enable_result.success:
                        log.status = RemediationStatus.SUCCESS

                        # Resolve any interface down alerts
                        alert_result = await db.execute(
                            select(Alert).where(
                                Alert.device_id == device_id,
                                Alert.alert_type == "interface_down",
                                Alert.status == AlertStatus.ACTIVE,
                            )
                        )
                        for alert in alert_result.scalars():
                            if alert.context and alert.context.get("interface") == interface_name:
                                alert.status = AlertStatus.RESOLVED
                                alert.resolved_at = datetime.utcnow()
                                alert.resolution_notes = "Interface re-enabled via remediation"
                    else:
                        log.status = RemediationStatus.FAILED
                        log.error_message = enable_result.error

                    log.completed_at = datetime.utcnow()
                    driver.disconnect()
                    await db.commit()

                    return {
                        "status": "success" if enable_result.success else "error",
                        "device_id": device_id,
                        "interface": interface_name,
                        "remediation_id": log.id,
                    }

                except Exception as e:
                    logger.error(f"Interface enable failed: {e}")
                    log.status = RemediationStatus.FAILED
                    log.error_message = str(e)
                    log.completed_at = datetime.utcnow()
                    await db.commit()

                    if driver and driver.is_connected:
                        driver.disconnect()

                    return {"status": "error", "error": str(e)}

            except Exception as e:
                logger.error(f"interface_enable failed: {e}")
                return {"status": "error", "error": str(e)}

    return run_async(_enable())


@celery_app.task(bind=True)
def clear_bgp_session(self, device_id: int, neighbor_ip: str):
    """Clear a BGP session."""
    logger.info(f"Clearing BGP session to {neighbor_ip} on device {device_id}")

    async def _clear_bgp():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Device).where(Device.id == device_id)
                )
                device = result.scalar_one_or_none()

                if not device:
                    return {"status": "error", "error": f"Device {device_id} not found"}

                log = await create_remediation_log(
                    db, device_id, "clear_bgp_session", "clear_bgp"
                )
                log.status = RemediationStatus.IN_PROGRESS
                log.started_at = datetime.utcnow()
                await db.flush()

                credentials = get_device_credentials(device)
                if not credentials.get("username"):
                    log.status = RemediationStatus.FAILED
                    log.error_message = "No credentials available"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {"status": "error", "error": "No credentials available"}

                driver = get_ssh_driver(device, credentials)
                if not driver:
                    log.status = RemediationStatus.FAILED
                    log.error_message = "Could not create SSH driver"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {"status": "error", "error": "Could not create driver"}

                try:
                    connect_result = driver.connect()
                    if not connect_result.success:
                        raise Exception(f"Connection failed: {connect_result.error}")

                    clear_result = driver.clear_bgp_neighbor(neighbor_ip)
                    log.commands_executed = [f"clear ip bgp {neighbor_ip} soft"]
                    log.command_output = clear_result.raw_output
                    log.status = (
                        RemediationStatus.SUCCESS
                        if clear_result.success
                        else RemediationStatus.FAILED
                    )
                    log.error_message = clear_result.error if not clear_result.success else None
                    log.completed_at = datetime.utcnow()

                    driver.disconnect()
                    await db.commit()

                    return {
                        "status": "success" if clear_result.success else "error",
                        "device_id": device_id,
                        "neighbor": neighbor_ip,
                        "remediation_id": log.id,
                    }

                except Exception as e:
                    logger.error(f"Clear BGP session failed: {e}")
                    log.status = RemediationStatus.FAILED
                    log.error_message = str(e)
                    log.completed_at = datetime.utcnow()
                    await db.commit()

                    if driver and driver.is_connected:
                        driver.disconnect()

                    return {"status": "error", "error": str(e)}

            except Exception as e:
                logger.error(f"clear_bgp_session failed: {e}")
                return {"status": "error", "error": str(e)}

    return run_async(_clear_bgp())


@celery_app.task(bind=True)
def clear_device_caches(self, device_id: int):
    """Clear device caches to free memory."""
    logger.info(f"Clearing caches on device {device_id}")

    async def _clear_caches():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Device).where(Device.id == device_id)
                )
                device = result.scalar_one_or_none()

                if not device:
                    return {"status": "error", "error": f"Device {device_id} not found"}

                log = await create_remediation_log(
                    db, device_id, "clear_caches", "clear_caches"
                )
                log.status = RemediationStatus.IN_PROGRESS
                log.started_at = datetime.utcnow()
                await db.flush()

                credentials = get_device_credentials(device)
                if not credentials.get("username"):
                    log.status = RemediationStatus.FAILED
                    log.error_message = "No credentials available"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {"status": "error", "error": "No credentials available"}

                driver = get_ssh_driver(device, credentials)
                if not driver:
                    log.status = RemediationStatus.FAILED
                    log.error_message = "Could not create SSH driver"
                    log.completed_at = datetime.utcnow()
                    await db.commit()
                    return {"status": "error", "error": "Could not create driver"}

                try:
                    connect_result = driver.connect()
                    if not connect_result.success:
                        raise Exception(f"Connection failed: {connect_result.error}")

                    # Commands to clear caches
                    cache_commands = [
                        "clear arp-cache",
                        "clear ip route *",
                    ]

                    log.commands_executed = cache_commands
                    outputs = []

                    for cmd in cache_commands:
                        cmd_result = driver.execute_command(cmd)
                        outputs.append(f"# {cmd}\n{cmd_result.raw_output or ''}")

                    log.command_output = "\n".join(outputs)
                    log.status = RemediationStatus.SUCCESS
                    log.completed_at = datetime.utcnow()

                    driver.disconnect()
                    await db.commit()

                    return {
                        "status": "success",
                        "device_id": device_id,
                        "commands_executed": len(cache_commands),
                        "remediation_id": log.id,
                    }

                except Exception as e:
                    logger.error(f"Clear caches failed: {e}")
                    log.status = RemediationStatus.FAILED
                    log.error_message = str(e)
                    log.completed_at = datetime.utcnow()
                    await db.commit()

                    if driver and driver.is_connected:
                        driver.disconnect()

                    return {"status": "error", "error": str(e)}

            except Exception as e:
                logger.error(f"clear_device_caches failed: {e}")
                return {"status": "error", "error": str(e)}

    return run_async(_clear_caches())


@celery_app.task(bind=True, max_retries=3)
def send_webhook_alert(self, alert_id: int):
    """Send alert notification via webhook."""
    logger.info(f"Sending webhook for alert {alert_id}")

    if not settings.webhook_url:
        logger.warning("Webhook URL not configured, skipping")
        return {"status": "skipped", "reason": "No webhook URL configured"}

    async def _send_webhook():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Alert).where(Alert.id == alert_id)
                )
                alert = result.scalar_one_or_none()

                if not alert:
                    return {"status": "error", "error": f"Alert {alert_id} not found"}

                # Get device info
                device_result = await db.execute(
                    select(Device).where(Device.id == alert.device_id)
                )
                device = device_result.scalar_one_or_none()

                # Build webhook payload
                payload = {
                    "alert_id": alert.id,
                    "title": alert.title,
                    "message": alert.message,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "alert_type": alert.alert_type,
                    "device": {
                        "id": device.id if device else None,
                        "name": device.name if device else "Unknown",
                        "ip_address": device.ip_address if device else None,
                    },
                    "context": alert.context,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None,
                }

                # Send webhook
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        settings.webhook_url,
                        json=payload,
                        timeout=settings.webhook_timeout_seconds,
                    )
                    response.raise_for_status()

                # Update alert
                alert.webhook_sent = True
                alert.webhook_sent_at = datetime.utcnow()
                await db.commit()

                logger.info(f"Webhook sent successfully for alert {alert_id}")
                return {
                    "status": "success",
                    "alert_id": alert_id,
                    "response_status": response.status_code,
                }

            except httpx.HTTPStatusError as e:
                logger.error(f"Webhook HTTP error: {e}")
                raise self.retry(exc=e, countdown=60)

            except httpx.RequestError as e:
                logger.error(f"Webhook request error: {e}")
                raise self.retry(exc=e, countdown=30)

            except Exception as e:
                logger.error(f"send_webhook_alert failed: {e}")
                return {"status": "error", "alert_id": alert_id, "error": str(e)}

    return run_async(_send_webhook())


@celery_app.task(bind=True)
def auto_remediate_alert(self, alert_id: int):
    """
    Automatically remediate an alert based on its type.

    This task decides which remediation action to take based on the alert type.
    """
    logger.info(f"Auto-remediating alert {alert_id}")

    async def _auto_remediate():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Alert).where(Alert.id == alert_id)
                )
                alert = result.scalar_one_or_none()

                if not alert:
                    return {"status": "error", "error": f"Alert {alert_id} not found"}

                if alert.status != AlertStatus.ACTIVE:
                    return {"status": "skipped", "reason": "Alert not active"}

                # Determine remediation action based on alert type patterns
                alert_type = alert.alert_type
                action = None
                param = None

                if alert_type == "interface_down" or alert_type.startswith("interface_down_"):
                    action = "interface_enable"
                    param = alert.context.get("interface") if alert.context else None
                elif alert_type == "memory_utilization":
                    action = "clear_caches"
                    param = None
                elif alert_type.startswith("bgp_neighbor_"):
                    action = "clear_bgp"
                    param = alert.context.get("neighbor") if alert.context else None
                elif alert_type.startswith("ospf_neighbor_"):
                    # OSPF doesn't have a clear command like BGP, skip for now
                    return {
                        "status": "skipped",
                        "reason": "OSPF neighbor issues require manual intervention",
                    }

                if action is None:
                    return {
                        "status": "skipped",
                        "reason": f"No auto-remediation configured for alert type: {alert_type}",
                    }

                if action == "interface_enable" and param:
                    # Trigger interface enable task
                    interface_enable.delay(alert.device_id, param)
                    return {
                        "status": "triggered",
                        "action": "interface_enable",
                        "interface": param,
                    }

                elif action == "clear_caches":
                    clear_device_caches.delay(alert.device_id)
                    return {"status": "triggered", "action": "clear_caches"}

                elif action == "clear_bgp" and param:
                    clear_bgp_session.delay(alert.device_id, param)
                    return {"status": "triggered", "action": "clear_bgp", "neighbor": param}

                return {"status": "skipped", "reason": "Missing required parameters"}

            except Exception as e:
                logger.error(f"auto_remediate_alert failed: {e}")
                return {"status": "error", "error": str(e)}

    return run_async(_auto_remediate())
