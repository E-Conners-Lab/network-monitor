"""Polling tasks for device monitoring."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.core.health_checks import ping_host
from src.drivers import ConnectionParams, DevicePlatform, SNMPDriver
from src.integrations.netbox import NetBoxSyncService
from src.models.alert import Alert, AlertSeverity, AlertStatus
from src.models.device import Device, DeviceType
from src.models.metric import Metric, MetricType
from src.tasks import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Singleton engine and session factory for connection pooling
_async_engine = None
_async_session_factory = None


def get_async_engine():
    """Get singleton async database engine for Celery tasks."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
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


# Alert thresholds
ALERT_THRESHOLDS = {
    MetricType.CPU_UTILIZATION: {"warning": 70.0, "critical": 90.0},
    MetricType.MEMORY_UTILIZATION: {"warning": 75.0, "critical": 95.0},
    MetricType.PING_LOSS: {"warning": 10.0, "critical": 50.0},
}


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
    unit: str | None = None,
    context: str | None = None,
    metadata: dict | None = None,
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


async def get_previous_metric(
    db: AsyncSession,
    device_id: int,
    metric_type: MetricType,
    context: str,
) -> Metric | None:
    """Get the most recent previous metric for rate calculation."""
    stmt = (
        select(Metric)
        .where(
            Metric.device_id == device_id,
            Metric.metric_type == metric_type,
            Metric.context == context,
        )
        .order_by(Metric.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def calculate_rate_bps(
    current_octets: float,
    previous_octets: float,
    current_time: datetime,
    previous_time: datetime,
) -> float | None:
    """Calculate traffic rate in bits per second from octet counter delta.

    Handles 32-bit counter wraps (max 4,294,967,295 bytes).
    Returns None if calculation is invalid.
    """
    if previous_time is None or current_time is None:
        return None

    # Calculate time delta in seconds
    time_delta = (current_time - previous_time).total_seconds()
    if time_delta <= 0:
        return None

    # Calculate octet delta, handling 32-bit counter wrap
    MAX_32BIT = 4294967295
    if current_octets >= previous_octets:
        octet_delta = current_octets - previous_octets
    else:
        # Counter wrapped
        octet_delta = (MAX_32BIT - previous_octets) + current_octets

    # Convert to bits per second (octets * 8 / seconds)
    rate_bps = (octet_delta * 8) / time_delta

    return rate_bps


async def check_interface_down_alert(
    db: AsyncSession,
    device_id: int,
    if_index: str,
    if_name: str,
    status: str,
    device_name: str,
    admin_status: str = "up",
) -> Alert | None:
    """Check if interface is down and create/resolve alert accordingly.

    Only creates alerts for non-management interfaces that go down.
    Skips interfaces that are administratively shutdown.
    Resolves existing alerts if interface is now admin-down.
    """
    # Skip management interfaces and loopbacks
    skip_patterns = ["Loopback", "Null", "VoIP-Null", "Management", "mgmt"]
    if any(pattern.lower() in if_name.lower() for pattern in skip_patterns):
        return None

    # Also skip interfaces that are likely not relevant (VLAN interfaces, etc.)
    # We only care about physical interfaces like GigabitEthernet, FastEthernet, etc.
    physical_patterns = ["GigabitEthernet", "FastEthernet", "Ethernet", "Serial", "Tunnel"]
    is_physical = any(pattern.lower() in if_name.lower() for pattern in physical_patterns)
    if not is_physical:
        return None

    alert_type = "interface_down"

    # Check for existing active OR acknowledged alert for this interface
    # We don't want to create duplicate alerts if user already acknowledged one
    stmt = select(Alert).where(
        Alert.device_id == device_id,
        Alert.alert_type == alert_type,
        Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
    )
    result = await db.execute(stmt)
    existing_alerts = result.scalars().all()

    # Find alert matching this specific interface
    existing_alert = None
    for alert in existing_alerts:
        if alert.context and alert.context.get("if_index") == if_index:
            existing_alert = alert
            break

    # If interface is administratively shutdown, resolve any existing alert and skip
    if admin_status == "down":
        if existing_alert:
            existing_alert.status = AlertStatus.RESOLVED
            existing_alert.resolved_at = datetime.utcnow()
            existing_alert.resolution_notes = f"Interface {if_name} was administratively shutdown (auto-resolved)"
            logger.info(f"Alert auto-resolved: Interface {if_name} on {device_name} was admin shutdown")
        return None

    if status == "down":
        if existing_alert:
            # Alert already exists (either active or acknowledged)
            return existing_alert
        else:
            # Create new interface down alert
            alert = Alert(
                device_id=device_id,
                title=f"Interface Down: {if_name}",
                message=f"Interface {if_name} on {device_name} is down",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.ACTIVE,
                alert_type=alert_type,
                context={"if_index": if_index, "interface": if_name},
            )
            db.add(alert)
            await db.flush()
            logger.warning(
                f"Alert created: Interface {if_name} down on device {device_name}"
            )
            return alert
    elif status == "up" and existing_alert:
        # Interface came back up - resolve the alert (whether it was active or acknowledged)
        existing_alert.status = AlertStatus.RESOLVED
        existing_alert.resolved_at = datetime.utcnow()
        existing_alert.resolution_notes = f"Interface {if_name} is now up (auto-resolved)"
        logger.info(f"Alert auto-resolved: Interface {if_name} on {device_name} is now up")

    return None


async def check_and_create_alert(
    db: AsyncSession,
    device_id: int,
    metric_type: MetricType,
    value: float,
    context: str | None = None,
) -> Alert | None:
    """Check if metric exceeds thresholds and create alert if needed."""
    thresholds = ALERT_THRESHOLDS.get(metric_type)
    if not thresholds:
        return None

    # Check for existing active or acknowledged alert
    # Don't create duplicates if user already acknowledged one
    stmt = select(Alert).where(
        Alert.device_id == device_id,
        Alert.alert_type == metric_type.value,
        Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
    )
    result = await db.execute(stmt)
    existing_alert = result.scalar_one_or_none()

    severity = None
    if value >= thresholds["critical"]:
        severity = AlertSeverity.CRITICAL
    elif value >= thresholds["warning"]:
        severity = AlertSeverity.WARNING

    if severity:
        if existing_alert:
            # Update severity if escalated
            if (
                severity == AlertSeverity.CRITICAL
                and existing_alert.severity == AlertSeverity.WARNING
            ):
                existing_alert.severity = severity
                existing_alert.message = f"{metric_type.value} is now CRITICAL: {value:.1f}%"
            return existing_alert
        else:
            # Create new alert
            alert = Alert(
                device_id=device_id,
                title=f"{metric_type.value.replace('_', ' ').title()} Alert",
                message=f"{metric_type.value}: {value:.1f}% exceeds {severity.value} threshold",
                severity=severity,
                status=AlertStatus.ACTIVE,
                alert_type=metric_type.value,
                context={"value": value, "interface": context} if context else {"value": value},
            )
            db.add(alert)
            await db.flush()
            logger.warning(
                f"Alert created: {alert.title} for device {device_id} - {value:.1f}%"
            )
            return alert
    elif existing_alert:
        # Value is now below threshold - resolve alert
        existing_alert.status = AlertStatus.RESOLVED
        existing_alert.resolved_at = datetime.utcnow()
        existing_alert.resolution_notes = f"Metric returned to normal: {value:.1f}%"
        logger.info(f"Alert resolved for device {device_id}: {metric_type.value}")

    return None


async def poll_device_metrics(db: AsyncSession, device: Device) -> dict:
    """Poll metrics from a single device using SNMP."""
    results = {
        "device_id": device.id,
        "device_name": device.name,
        "success": False,
        "metrics": [],
        "alerts": [],
        "errors": [],
    }

    # Ping check - use 3 pings with 3s timeout for better accuracy
    # This balances speed with reliability (avoids false positives from single dropped packet)
    ping_result = await ping_host(device.ip_address, count=3, timeout=3)

    # Retry once if ping fails (helps with momentary network glitches)
    if not ping_result.success:
        await asyncio.sleep(0.5)  # Brief delay before retry
        ping_result = await ping_host(device.ip_address, count=3, timeout=3)

    if ping_result.success:
        results["metrics"].append(
            {
                "type": MetricType.PING_LATENCY.value,
                "value": ping_result.latency_ms or 0,
            }
        )
        results["metrics"].append(
            {"type": MetricType.PING_LOSS.value, "value": ping_result.packet_loss}
        )

        # Store ping metrics
        if ping_result.latency_ms is not None:
            await store_metric(
                db,
                device.id,
                MetricType.PING_LATENCY,
                ping_result.latency_ms,
                "ping_latency",
                unit="ms",
            )

        await store_metric(
            db,
            device.id,
            MetricType.PING_LOSS,
            ping_result.packet_loss,
            "ping_packet_loss",
            unit="%",
        )

        # Check for packet loss alert
        alert = await check_and_create_alert(
            db, device.id, MetricType.PING_LOSS, ping_result.packet_loss
        )
        if alert:
            results["alerts"].append(alert.id)

        # Resolve any existing device_unreachable alerts since ping succeeded
        stmt = select(Alert).where(
            Alert.device_id == device.id,
            Alert.alert_type == "device_unreachable",
            Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
        )
        result = await db.execute(stmt)
        unreachable_alerts = result.scalars().all()
        for unreachable_alert in unreachable_alerts:
            unreachable_alert.status = AlertStatus.RESOLVED
            unreachable_alert.resolved_at = datetime.utcnow()
            unreachable_alert.resolution_notes = f"Device {device.name} is now responding to ping (auto-resolved)"
            logger.info(f"Alert auto-resolved: Device {device.name} is now reachable")
    else:
        results["errors"].append(f"Ping failed: {ping_result.error}")
        # Create unreachable alert
        stmt = select(Alert).where(
            Alert.device_id == device.id,
            Alert.alert_type == "device_unreachable",
            Alert.status == AlertStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            alert = Alert(
                device_id=device.id,
                title="Device Unreachable",
                message=f"Device {device.name} ({device.ip_address}) is not responding to ping",
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACTIVE,
                alert_type="device_unreachable",
            )
            db.add(alert)
            await db.flush()
            results["alerts"].append(alert.id)

        # Update device status and return early - skip SNMP if ping fails
        device.is_reachable = False
        return results

    # SNMP polling - only if ping succeeded
    snmp_community = device.snmp_community or settings.snmp_community
    try:
        params = ConnectionParams(
            host=device.ip_address,
            snmp_community=snmp_community,
            timeout=settings.snmp_timeout_seconds,
        )
        snmp_driver = SNMPDriver(params)
        connect_result = snmp_driver.connect()

        if not connect_result.success:
            logger.warning(f"Device {device.name} ({device.ip_address}): SNMP connect failed: {connect_result.error}")

        if connect_result.success:
            # Get CPU utilization
            cpu_result = snmp_driver.get_cpu_utilization()
            if cpu_result.success and cpu_result.data is not None:
                # Extract 5-minute CPU average from the dict
                cpu_data = cpu_result.data
                raw_cpu = cpu_data.get("cpu_5min", cpu_data.get("cpu_1min", 0))
                # Handle "No Such Instance" errors from unsupported OIDs
                # Values can be numeric or string representation of numbers
                if raw_cpu is not None:
                    # Skip SNMP error strings like "No Such Instance..."
                    if isinstance(raw_cpu, str) and "No Such" in raw_cpu:
                        pass
                    else:
                        try:
                            cpu_value = float(raw_cpu)
                            results["metrics"].append(
                                {"type": MetricType.CPU_UTILIZATION.value, "value": cpu_value}
                            )
                            await store_metric(
                                db,
                                device.id,
                                MetricType.CPU_UTILIZATION,
                                cpu_value,
                                "cpu_utilization",
                                unit="%",
                            )
                            alert = await check_and_create_alert(
                                db, device.id, MetricType.CPU_UTILIZATION, cpu_value
                            )
                            if alert:
                                results["alerts"].append(alert.id)
                        except (ValueError, TypeError):
                            pass  # Skip if value can't be converted

            # Get memory utilization
            memory_result = snmp_driver.get_memory_utilization()
            if memory_result.success and memory_result.data is not None:
                # Extract memory utilization percentage from the dict
                memory_data = memory_result.data
                raw_memory = memory_data.get("memory_utilization", 0)
                # Handle "No Such Instance" errors from unsupported OIDs
                # Values can be numeric or string representation of numbers
                if raw_memory is not None:
                    # Skip SNMP error strings like "No Such Instance..."
                    if isinstance(raw_memory, str) and "No Such" in raw_memory:
                        pass
                    else:
                        try:
                            memory_value = float(raw_memory)
                            results["metrics"].append(
                                {"type": MetricType.MEMORY_UTILIZATION.value, "value": memory_value}
                            )
                            await store_metric(
                                db,
                                device.id,
                                MetricType.MEMORY_UTILIZATION,
                                memory_value,
                                "memory_utilization",
                                unit="%",
                            )
                            alert = await check_and_create_alert(
                                db, device.id, MetricType.MEMORY_UTILIZATION, memory_value
                            )
                            if alert:
                                results["alerts"].append(alert.id)
                        except (ValueError, TypeError):
                            pass  # Skip if value can't be converted

            # Get interface names first (ifDescr) to map if_index to real names
            interface_names = {}
            names_result = snmp_driver.get_interface_names()
            if names_result.success and names_result.data:
                interface_names = names_result.data
                logger.info(f"Device {device.name}: Found {len(interface_names)} interfaces")
            else:
                logger.warning(f"Device {device.name}: Failed to get interface names: {names_result.error}")

            # Get interface statuses
            # get_interface_status returns {if_index: status_string} like {"1": "up", "2": "down"}
            interfaces = snmp_driver.get_interface_status()
            if interfaces.success and interfaces.data:
                logger.info(f"Device {device.name}: Got status for {len(interfaces.data)} interfaces")
            else:
                logger.warning(f"Device {device.name}: Failed to get interface status: {interfaces.error if interfaces else 'None'}")

            # Get admin status to filter out administratively shutdown interfaces
            admin_statuses = {}
            admin_result = snmp_driver.get_interface_admin_status()
            if admin_result.success and admin_result.data:
                admin_statuses = admin_result.data

            if interfaces.success and interfaces.data:
                for if_index, status in interfaces.data.items():
                    if_name = interface_names.get(if_index, f"Interface {if_index}")
                    admin_status = admin_statuses.get(if_index, "up")

                    # Store interface status (1=up, 0=down)
                    status_value = 1.0 if status == "up" else 0.0
                    await store_metric(
                        db,
                        device.id,
                        MetricType.INTERFACE_STATUS,
                        status_value,
                        f"interface_{if_index}_status",
                        context=f"if_index_{if_index}",
                        metadata={"if_index": if_index, "status": status, "if_name": if_name, "admin_status": admin_status},
                    )

                    # Check for interface down alerts (skip admin-shutdown interfaces)
                    alert = await check_interface_down_alert(
                        db, device.id, if_index, if_name, status, device.name, admin_status
                    )
                    if alert:
                        results["alerts"].append(alert.id)

                    # Get traffic counters for each interface
                    try:
                        counters = snmp_driver.get_interface_counters(int(if_index))
                        if counters.success and counters.data:
                            # Store in/out octets (values may be strings from SNMP)
                            in_octets_raw = counters.data.get("in_octets", 0)
                            out_octets_raw = counters.data.get("out_octets", 0)
                            in_errors_raw = counters.data.get("in_errors", 0)
                            out_errors_raw = counters.data.get("out_errors", 0)
                            current_time = datetime.utcnow()
                            context_str = f"if_index_{if_index}"

                            # Process IN octets and calculate rate
                            try:
                                in_octets = float(in_octets_raw)

                                # Get previous in_octets for rate calculation
                                prev_in = await get_previous_metric(
                                    db, device.id, MetricType.INTERFACE_IN_OCTETS, context_str
                                )

                                # Store current counter
                                await store_metric(
                                    db,
                                    device.id,
                                    MetricType.INTERFACE_IN_OCTETS,
                                    in_octets,
                                    f"interface_{if_index}_in_octets",
                                    unit="bytes",
                                    context=context_str,
                                    metadata={"if_name": if_name},
                                )

                                # Calculate and store rate if we have previous data
                                if prev_in:
                                    in_rate = calculate_rate_bps(
                                        in_octets, prev_in.value, current_time, prev_in.created_at
                                    )
                                    if in_rate is not None and in_rate >= 0:
                                        await store_metric(
                                            db,
                                            device.id,
                                            MetricType.INTERFACE_IN_RATE,
                                            in_rate,
                                            f"interface_{if_index}_in_rate",
                                            unit="bps",
                                            context=context_str,
                                            metadata={"if_name": if_name},
                                        )
                            except (ValueError, TypeError):
                                pass

                            # Process OUT octets and calculate rate
                            try:
                                out_octets = float(out_octets_raw)

                                # Get previous out_octets for rate calculation
                                prev_out = await get_previous_metric(
                                    db, device.id, MetricType.INTERFACE_OUT_OCTETS, context_str
                                )

                                # Store current counter
                                await store_metric(
                                    db,
                                    device.id,
                                    MetricType.INTERFACE_OUT_OCTETS,
                                    out_octets,
                                    f"interface_{if_index}_out_octets",
                                    unit="bytes",
                                    context=context_str,
                                    metadata={"if_name": if_name},
                                )

                                # Calculate and store rate if we have previous data
                                if prev_out:
                                    out_rate = calculate_rate_bps(
                                        out_octets, prev_out.value, current_time, prev_out.created_at
                                    )
                                    if out_rate is not None and out_rate >= 0:
                                        await store_metric(
                                            db,
                                            device.id,
                                            MetricType.INTERFACE_OUT_RATE,
                                            out_rate,
                                            f"interface_{if_index}_out_rate",
                                            unit="bps",
                                            context=context_str,
                                            metadata={"if_name": if_name},
                                        )
                            except (ValueError, TypeError):
                                pass

                            try:
                                in_errors = float(in_errors_raw)
                                if in_errors > 0:
                                    await store_metric(
                                        db,
                                        device.id,
                                        MetricType.INTERFACE_IN_ERRORS,
                                        in_errors,
                                        f"interface_{if_index}_in_errors",
                                        context=context_str,
                                        metadata={"if_name": if_name},
                                    )
                            except (ValueError, TypeError):
                                pass

                            try:
                                out_errors = float(out_errors_raw)
                                if out_errors > 0:
                                    await store_metric(
                                        db,
                                        device.id,
                                        MetricType.INTERFACE_OUT_ERRORS,
                                        out_errors,
                                        f"interface_{if_index}_out_errors",
                                        context=context_str,
                                        metadata={"if_name": if_name},
                                    )
                            except (ValueError, TypeError):
                                pass
                    except Exception as e:
                        logger.debug(f"Could not get counters for interface {if_index}: {e}")

            snmp_driver.disconnect()
            results["success"] = True
        else:
            results["errors"].append(f"SNMP connection failed: {connect_result.error}")

    except Exception as e:
        logger.error(f"SNMP polling error for {device.name}: {e}")
        results["errors"].append(f"SNMP error: {str(e)}")

    # Update device status
    device.is_reachable = results["success"] or ping_result.success
    if device.is_reachable:
        device.last_seen = datetime.utcnow().isoformat()

    return results


# Maximum concurrent device polls to avoid overwhelming the network/database
# Increased to 10 for faster overall polling with 22 devices
MAX_CONCURRENT_POLLS = 10


async def poll_device_with_session(device: Device, session_factory) -> dict:
    """Poll a single device with its own database session for concurrent execution."""
    async with session_factory() as db:
        try:
            # Fetch device fresh in this session so changes are tracked
            result = await db.execute(
                select(Device).where(Device.id == device.id)
            )
            fresh_device = result.scalar_one_or_none()
            if not fresh_device:
                return {
                    "device_id": device.id,
                    "device_name": device.name,
                    "success": False,
                    "error": "Device not found",
                }
            result = await poll_device_metrics(db, fresh_device)
            await db.commit()
            return result
        except Exception as e:
            logger.error(f"Error polling device {device.name}: {e}")
            await db.rollback()
            return {
                "device_id": device.id,
                "device_name": device.name,
                "success": False,
                "error": str(e),
            }


@celery_app.task(bind=True)
def poll_all_devices(self):
    """Poll all active devices for metrics using parallel execution."""
    logger.info(f"Starting poll_all_devices task: {self.request.id}")

    async def _poll_all():
        AsyncSessionLocal = get_async_session()

        # Get device list in a separate session
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Device).where(Device.is_active == True)
            )
            devices = result.scalars().all()

        if not devices:
            logger.info("No active devices to poll")
            return {"status": "success", "devices_polled": 0, "results": []}

        logger.info(f"Polling {len(devices)} active devices with max {MAX_CONCURRENT_POLLS} concurrent")

        # Use semaphore to limit concurrent polls
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_POLLS)

        async def poll_with_semaphore(device):
            async with semaphore:
                return await poll_device_with_session(device, AsyncSessionLocal)

        # Poll all devices concurrently (limited by semaphore)
        results = await asyncio.gather(
            *[poll_with_semaphore(device) for device in devices],
            return_exceptions=True
        )

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception polling device {devices[i].name}: {result}")
                processed_results.append({
                    "device_id": devices[i].id,
                    "device_name": devices[i].name,
                    "success": False,
                    "error": str(result),
                })
            else:
                processed_results.append(result)
                logger.info(
                    f"Polled device {result['device_name']}: success={result['success']}, "
                    f"metrics={len(result.get('metrics', []))}, alerts={len(result.get('alerts', []))}"
                )

        return {
            "status": "success",
            "task_id": self.request.id,
            "devices_polled": len(devices),
            "successful": sum(1 for r in processed_results if r.get("success")),
            "failed": sum(1 for r in processed_results if not r.get("success")),
            "total_alerts": sum(len(r.get("alerts", [])) for r in processed_results),
        }

    return run_async(_poll_all())


@celery_app.task(bind=True)
def poll_device(self, device_id: int):
    """Poll a specific device for metrics."""
    logger.info(f"Starting poll_device task for device {device_id}")

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

                poll_result = await poll_device_metrics(db, device)
                await db.commit()

                return {
                    "status": "success",
                    "device_id": device_id,
                    **poll_result,
                }

            except Exception as e:
                logger.error(f"poll_device failed for {device_id}: {e}")
                await db.rollback()
                return {"status": "error", "device_id": device_id, "error": str(e)}

    return run_async(_poll_device())


@celery_app.task(bind=True)
def sync_netbox_devices(self):
    """Sync devices from NetBox."""
    logger.info(f"Starting sync_netbox_devices task: {self.request.id}")

    async def _sync():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                sync_service = NetBoxSyncService()

                if not sync_service.client.is_configured:
                    logger.warning("NetBox not configured, skipping sync")
                    return {
                        "status": "skipped",
                        "reason": "NetBox not configured (missing token)",
                    }

                result = await sync_service.sync_devices(db)
                return {
                    "status": "success" if result.get("success") else "error",
                    "task_id": self.request.id,
                    **result,
                }

            except Exception as e:
                logger.error(f"sync_netbox_devices failed: {e}")
                return {"status": "error", "error": str(e)}

    return run_async(_sync())


@celery_app.task(bind=True)
def check_device_connectivity(self, device_id: int):
    """Check connectivity to a device (ping, SNMP, SSH)."""
    from src.core.health_checks import check_device_connectivity as _check_connectivity

    logger.info(f"Starting connectivity check for device {device_id}")

    async def _check():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Device).where(Device.id == device_id)
                )
                device = result.scalar_one_or_none()

                if not device:
                    return {"status": "error", "error": f"Device {device_id} not found"}

                # Map device type to platform
                platform_map = {
                    DeviceType.ROUTER: DevicePlatform.CISCO_IOS,
                    DeviceType.SWITCH: DevicePlatform.CISCO_IOS,
                    DeviceType.FIREWALL: DevicePlatform.CISCO_ASA,
                }
                platform = platform_map.get(device.device_type, DevicePlatform.CISCO_IOS)

                check_result = await _check_connectivity(
                    device_id=device.id,
                    device_name=device.name,
                    ip_address=device.ip_address,
                    snmp_community=device.snmp_community or settings.snmp_community,
                    platform=platform,
                    check_ping=True,
                    check_snmp=True,
                    check_ssh=False,  # No credentials in background task
                )

                # Update device status
                device.is_reachable = check_result.overall_reachable
                if check_result.overall_reachable:
                    device.last_seen = datetime.utcnow().isoformat()
                await db.commit()

                return {
                    "status": "success",
                    "device_id": device_id,
                    "device_name": device.name,
                    "is_reachable": check_result.overall_reachable,
                    "ping": {
                        "success": check_result.ping.success if check_result.ping else False,
                        "latency_ms": check_result.ping.latency_ms if check_result.ping else None,
                    } if check_result.ping else None,
                    "snmp": check_result.snmp,
                }

            except Exception as e:
                logger.error(f"check_device_connectivity failed for {device_id}: {e}")
                return {"status": "error", "device_id": device_id, "error": str(e)}

    return run_async(_check())


@celery_app.task(bind=True)
def cleanup_old_metrics(self, days_to_keep: int = 30):
    """Clean up old metric data to prevent database bloat."""
    from datetime import timedelta

    logger.info(f"Starting cleanup_old_metrics task: keeping {days_to_keep} days")

    async def _cleanup():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                from sqlalchemy import delete

                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

                # Delete old metrics
                stmt = delete(Metric).where(Metric.created_at < cutoff_date)
                result = await db.execute(stmt)
                deleted_count = result.rowcount

                await db.commit()

                logger.info(f"Deleted {deleted_count} old metrics")
                return {
                    "status": "success",
                    "task_id": self.request.id,
                    "deleted_metrics": deleted_count,
                    "cutoff_date": cutoff_date.isoformat(),
                }

            except Exception as e:
                logger.error(f"cleanup_old_metrics failed: {e}")
                await db.rollback()
                return {"status": "error", "error": str(e)}

    return run_async(_cleanup())
