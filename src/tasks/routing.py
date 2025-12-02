"""Routing protocol monitoring tasks using pyATS/Genie."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.tasks import celery_app
from src.config import get_settings
from src.models.device import Device, DeviceType
from src.models.metric import Metric, MetricType
from src.models.alert import Alert, AlertSeverity, AlertStatus
from src.drivers import ConnectionParams, DevicePlatform, PyATSDriver
from src.drivers.pyats_driver import extract_bgp_neighbor_states, extract_ospf_neighbor_states

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


async def store_metric(
    db: AsyncSession,
    device_id: int,
    metric_type: MetricType,
    value: float,
    metric_name: str,
    unit: Optional[str] = None,
    context: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Metric:
    """Store a metric in the database."""
    metric = Metric(
        device_id=device_id,
        metric_type=metric_type,
        metric_name=metric_name,
        value=value,
        unit=unit,
        context=context,
        metadata_=metadata,
    )
    db.add(metric)
    await db.flush()
    return metric


async def check_neighbor_alert(
    db: AsyncSession,
    device_id: int,
    neighbor_type: str,  # "bgp" or "ospf"
    neighbor_id: str,
    state: str,
    previous_state: Optional[str],
) -> Optional[Alert]:
    """Check for neighbor state changes and create alerts."""
    # Define "bad" states
    bgp_bad_states = ["idle", "active", "connect", "opensent", "openconfirm"]
    ospf_bad_states = ["down", "attempt", "init", "2-way"]

    is_down = False
    if neighbor_type == "bgp":
        is_down = state.lower() in bgp_bad_states
    else:
        is_down = state.lower() in ospf_bad_states

    alert_type = f"{neighbor_type}_neighbor_{neighbor_id}"

    # Check for existing alert
    stmt = select(Alert).where(
        Alert.device_id == device_id,
        Alert.alert_type == alert_type,
        Alert.status == AlertStatus.ACTIVE,
    )
    result = await db.execute(stmt)
    existing_alert = result.scalar_one_or_none()

    if is_down:
        if not existing_alert:
            # Create new alert
            alert = Alert(
                device_id=device_id,
                title=f"{neighbor_type.upper()} Neighbor Down",
                message=f"{neighbor_type.upper()} neighbor {neighbor_id} is in state: {state}",
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACTIVE,
                alert_type=alert_type,
                context={"neighbor": neighbor_id, "state": state, "type": neighbor_type},
            )
            db.add(alert)
            await db.flush()
            logger.warning(f"Alert: {neighbor_type.upper()} neighbor {neighbor_id} is {state}")
            return alert
        return existing_alert
    elif existing_alert:
        # Neighbor came back up - resolve alert
        existing_alert.status = AlertStatus.RESOLVED
        existing_alert.resolved_at = datetime.utcnow()
        existing_alert.resolution_notes = f"Neighbor recovered to state: {state}"
        logger.info(f"{neighbor_type.upper()} neighbor {neighbor_id} recovered to {state}")

    return None


async def poll_bgp_neighbors(db: AsyncSession, device: Device, driver: PyATSDriver) -> dict:
    """Poll BGP neighbors for a device."""
    results = {
        "neighbors_polled": 0,
        "neighbors_established": 0,
        "neighbors_down": 0,
        "alerts_created": 0,
    }

    bgp_result = driver.get_bgp_neighbors()
    if not bgp_result.success:
        logger.warning(f"Failed to get BGP neighbors for {device.name}: {bgp_result.error}")
        return results

    neighbors = extract_bgp_neighbor_states(bgp_result.data)
    results["neighbors_polled"] = len(neighbors)

    for neighbor in neighbors:
        neighbor_ip = neighbor.get("neighbor", "unknown")
        state = neighbor.get("state", "unknown")
        vrf = neighbor.get("vrf", "default")
        remote_as = neighbor.get("remote_as", "N/A")
        prefixes = neighbor.get("prefixes_received", 0)

        # Store metric
        context_str = f"bgp_neighbor_{neighbor_ip}"
        state_value = 1.0 if state.lower() == "established" else 0.0

        await store_metric(
            db,
            device.id,
            MetricType.BGP_NEIGHBOR_STATE,
            state_value,
            f"bgp_neighbor_{neighbor_ip}_state",
            context=context_str,
            metadata={
                "neighbor": neighbor_ip,
                "state": state,
                "vrf": vrf,
                "remote_as": str(remote_as),
                "prefixes_received": prefixes,
            },
        )

        if state.lower() == "established":
            results["neighbors_established"] += 1
        else:
            results["neighbors_down"] += 1

        # Check for alerts
        alert = await check_neighbor_alert(
            db, device.id, "bgp", neighbor_ip, state, None
        )
        if alert and alert.status == AlertStatus.ACTIVE:
            results["alerts_created"] += 1

    return results


async def poll_ospf_neighbors(db: AsyncSession, device: Device, driver: PyATSDriver) -> dict:
    """Poll OSPF neighbors for a device."""
    results = {
        "neighbors_polled": 0,
        "neighbors_full": 0,
        "neighbors_down": 0,
        "alerts_created": 0,
    }

    ospf_result = driver.get_ospf_neighbors()
    if not ospf_result.success:
        logger.warning(f"Failed to get OSPF neighbors for {device.name}: {ospf_result.error}")
        return results

    neighbors = extract_ospf_neighbor_states(ospf_result.data)
    results["neighbors_polled"] = len(neighbors)

    for neighbor in neighbors:
        neighbor_id = neighbor.get("neighbor_id", "unknown")
        state = neighbor.get("state", "unknown")
        interface = neighbor.get("interface", "unknown")
        address = neighbor.get("address", "N/A")

        # Store metric
        context_str = f"ospf_neighbor_{neighbor_id}"
        # Check if state contains "full" (handles "FULL/  -", "FULL/DR", "FULL/BDR", etc.)
        state_value = 1.0 if "full" in state.lower() else 0.0

        await store_metric(
            db,
            device.id,
            MetricType.OSPF_NEIGHBOR_STATE,
            state_value,
            f"ospf_neighbor_{neighbor_id}_state",
            context=context_str,
            metadata={
                "neighbor_id": neighbor_id,
                "state": state,
                "interface": interface,
                "address": address,
            },
        )

        if "full" in state.lower():
            results["neighbors_full"] += 1
        else:
            results["neighbors_down"] += 1

        # Check for alerts
        alert = await check_neighbor_alert(
            db, device.id, "ospf", neighbor_id, state, None
        )
        if alert and alert.status == AlertStatus.ACTIVE:
            results["alerts_created"] += 1

    return results


async def poll_device_routing(db: AsyncSession, device: Device) -> dict:
    """Poll routing protocol neighbors for a device using pyATS."""
    results = {
        "device_id": device.id,
        "device_name": device.name,
        "success": False,
        "bgp": {},
        "ospf": {},
        "errors": [],
    }

    # Get SSH credentials from device tags or settings
    username = device.tags.get("ssh_username") if device.tags else None
    password = device.tags.get("ssh_password") if device.tags else None

    if not username or not password:
        # Try settings defaults
        username = settings.ssh_username if hasattr(settings, "ssh_username") else None
        password = settings.ssh_password if hasattr(settings, "ssh_password") else None

    if not username or not password:
        results["errors"].append("No SSH credentials available")
        logger.warning(f"No SSH credentials for {device.name}, skipping routing poll")
        return results

    # Map device type to platform
    platform_map = {
        DeviceType.ROUTER: DevicePlatform.CISCO_IOS_XE,  # CSR1000v
        DeviceType.SWITCH: DevicePlatform.CISCO_IOS,
        DeviceType.FIREWALL: DevicePlatform.CISCO_ASA,
    }
    platform = platform_map.get(device.device_type, DevicePlatform.CISCO_IOS)

    params = ConnectionParams(
        host=device.ip_address,
        username=username,
        password=password,
        port=device.ssh_port,
        platform=platform,
    )

    try:
        driver = PyATSDriver(params)
        connect_result = driver.connect()

        if not connect_result.success:
            results["errors"].append(f"pyATS connection failed: {connect_result.error}")
            return results

        try:
            # Poll BGP
            results["bgp"] = await poll_bgp_neighbors(db, device, driver)

            # Poll OSPF
            results["ospf"] = await poll_ospf_neighbors(db, device, driver)

            results["success"] = True
        finally:
            driver.disconnect()

    except ImportError as e:
        results["errors"].append(f"pyATS not installed: {e}")
        logger.error(f"pyATS not available: {e}")
    except Exception as e:
        results["errors"].append(str(e))
        logger.error(f"Routing poll error for {device.name}: {e}")

    return results


@celery_app.task(bind=True)
def poll_routing_protocols(self):
    """Poll BGP/OSPF neighbors for all devices with routing protocols."""
    logger.info(f"Starting poll_routing_protocols task: {self.request.id}")

    async def _poll_all():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                # Get all active routers
                result = await db.execute(
                    select(Device).where(
                        Device.is_active == True,
                        Device.device_type == DeviceType.ROUTER,
                    )
                )
                devices = result.scalars().all()

                if not devices:
                    logger.info("No active routers to poll for routing protocols")
                    return {"status": "success", "devices_polled": 0}

                results = []
                total_bgp_neighbors = 0
                total_ospf_neighbors = 0
                total_alerts = 0

                for device in devices:
                    try:
                        poll_result = await poll_device_routing(db, device)
                        results.append(poll_result)

                        if poll_result.get("success"):
                            total_bgp_neighbors += poll_result.get("bgp", {}).get(
                                "neighbors_polled", 0
                            )
                            total_ospf_neighbors += poll_result.get("ospf", {}).get(
                                "neighbors_polled", 0
                            )
                            total_alerts += poll_result.get("bgp", {}).get(
                                "alerts_created", 0
                            )
                            total_alerts += poll_result.get("ospf", {}).get(
                                "alerts_created", 0
                            )

                        logger.info(
                            f"Routing poll for {device.name}: success={poll_result['success']}, "
                            f"BGP neighbors={poll_result.get('bgp', {}).get('neighbors_polled', 0)}, "
                            f"OSPF neighbors={poll_result.get('ospf', {}).get('neighbors_polled', 0)}"
                        )
                    except Exception as e:
                        logger.error(f"Error polling routing for {device.name}: {e}")
                        results.append({
                            "device_id": device.id,
                            "device_name": device.name,
                            "success": False,
                            "error": str(e),
                        })

                await db.commit()

                return {
                    "status": "success",
                    "task_id": self.request.id,
                    "devices_polled": len(devices),
                    "successful": sum(1 for r in results if r.get("success")),
                    "failed": sum(1 for r in results if not r.get("success")),
                    "total_bgp_neighbors": total_bgp_neighbors,
                    "total_ospf_neighbors": total_ospf_neighbors,
                    "total_alerts": total_alerts,
                }

            except Exception as e:
                logger.error(f"poll_routing_protocols failed: {e}")
                await db.rollback()
                return {"status": "error", "error": str(e)}

    return run_async(_poll_all())


@celery_app.task(bind=True)
def poll_device_routing_task(self, device_id: int):
    """Poll routing protocols for a specific device."""
    logger.info(f"Starting routing poll for device {device_id}")

    async def _poll_device():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Device).where(Device.id == device_id)
                )
                device = result.scalar_one_or_none()

                if not device:
                    return {"status": "error", "error": f"Device {device_id} not found"}

                poll_result = await poll_device_routing(db, device)
                await db.commit()

                return {
                    "status": "success",
                    "device_id": device_id,
                    **poll_result,
                }

            except Exception as e:
                logger.error(f"poll_device_routing failed for {device_id}: {e}")
                await db.rollback()
                return {"status": "error", "device_id": device_id, "error": str(e)}

    return run_async(_poll_device())
