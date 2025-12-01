"""Polling tasks for device monitoring."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.tasks import celery_app
from src.config import get_settings
from src.models.device import Device, DeviceType
from src.models.metric import Metric, MetricType
from src.models.alert import Alert, AlertSeverity, AlertStatus
from src.drivers import ConnectionParams, DevicePlatform, SNMPDriver
from src.core.health_checks import ping_host
from src.integrations.netbox import NetBoxSyncService

logger = logging.getLogger(__name__)
settings = get_settings()


def get_async_engine():
    """Get async database engine for Celery tasks."""
    return create_async_engine(settings.database_url, echo=settings.debug)


def get_async_session():
    """Get async session factory."""
    engine = get_async_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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


async def check_and_create_alert(
    db: AsyncSession,
    device_id: int,
    metric_type: MetricType,
    value: float,
    context: Optional[str] = None,
) -> Optional[Alert]:
    """Check if metric exceeds thresholds and create alert if needed."""
    thresholds = ALERT_THRESHOLDS.get(metric_type)
    if not thresholds:
        return None

    # Check for existing active alert
    stmt = select(Alert).where(
        Alert.device_id == device_id,
        Alert.alert_type == metric_type.value,
        Alert.status == AlertStatus.ACTIVE,
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

    # Ping check
    ping_result = await ping_host(device.ip_address, count=3, timeout=5)
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

    # SNMP polling
    snmp_community = device.snmp_community or settings.snmp_community
    try:
        params = ConnectionParams(
            host=device.ip_address,
            snmp_community=snmp_community,
            timeout=settings.snmp_timeout_seconds,
        )
        snmp_driver = SNMPDriver(params)
        connect_result = snmp_driver.connect()

        if connect_result.success:
            # Get CPU utilization
            cpu_result = snmp_driver.get_cpu_utilization()
            if cpu_result.success and cpu_result.data is not None:
                # Extract 5-minute CPU average from the dict
                cpu_data = cpu_result.data
                raw_cpu = cpu_data.get("cpu_5min", cpu_data.get("cpu_1min", 0))
                # Handle "No Such Instance" errors from unsupported OIDs
                if raw_cpu is not None and not isinstance(raw_cpu, str):
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
                if raw_memory is not None and not isinstance(raw_memory, str):
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

            # Get interface statuses
            # get_interface_status returns {if_index: status_string} like {"1": "up", "2": "down"}
            interfaces = snmp_driver.get_interface_status()
            if interfaces.success and interfaces.data:
                for if_index, status in interfaces.data.items():
                    if_name = interface_names.get(if_index, f"Interface {if_index}")

                    # Store interface status (1=up, 0=down)
                    status_value = 1.0 if status == "up" else 0.0
                    await store_metric(
                        db,
                        device.id,
                        MetricType.INTERFACE_STATUS,
                        status_value,
                        f"interface_{if_index}_status",
                        context=f"if_index_{if_index}",
                        metadata={"if_index": if_index, "status": status, "if_name": if_name},
                    )

                    # Get traffic counters for each interface
                    try:
                        counters = snmp_driver.get_interface_counters(int(if_index))
                        if counters.success and counters.data:
                            # Store in/out octets (values may be strings from SNMP)
                            in_octets_raw = counters.data.get("in_octets", 0)
                            out_octets_raw = counters.data.get("out_octets", 0)
                            in_errors_raw = counters.data.get("in_errors", 0)
                            out_errors_raw = counters.data.get("out_errors", 0)

                            try:
                                in_octets = float(in_octets_raw)
                                await store_metric(
                                    db,
                                    device.id,
                                    MetricType.INTERFACE_IN_OCTETS,
                                    in_octets,
                                    f"interface_{if_index}_in_octets",
                                    unit="bytes",
                                    context=f"if_index_{if_index}",
                                    metadata={"if_name": if_name},
                                )
                            except (ValueError, TypeError):
                                pass

                            try:
                                out_octets = float(out_octets_raw)
                                await store_metric(
                                    db,
                                    device.id,
                                    MetricType.INTERFACE_OUT_OCTETS,
                                    out_octets,
                                    f"interface_{if_index}_out_octets",
                                    unit="bytes",
                                    context=f"if_index_{if_index}",
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
                                        context=f"if_index_{if_index}",
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
                                        context=f"if_index_{if_index}",
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


@celery_app.task(bind=True)
def poll_all_devices(self):
    """Poll all active devices for metrics."""
    logger.info(f"Starting poll_all_devices task: {self.request.id}")

    async def _poll_all():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            try:
                # Get all active devices
                result = await db.execute(
                    select(Device).where(Device.is_active == True)
                )
                devices = result.scalars().all()

                if not devices:
                    logger.info("No active devices to poll")
                    return {"status": "success", "devices_polled": 0, "results": []}

                results = []
                for device in devices:
                    try:
                        poll_result = await poll_device_metrics(db, device)
                        results.append(poll_result)
                        logger.info(
                            f"Polled device {device.name}: success={poll_result['success']}, "
                            f"metrics={len(poll_result['metrics'])}, alerts={len(poll_result['alerts'])}"
                        )
                    except Exception as e:
                        logger.error(f"Error polling device {device.name}: {e}")
                        results.append(
                            {
                                "device_id": device.id,
                                "device_name": device.name,
                                "success": False,
                                "error": str(e),
                            }
                        )

                await db.commit()

                return {
                    "status": "success",
                    "task_id": self.request.id,
                    "devices_polled": len(devices),
                    "successful": sum(1 for r in results if r.get("success")),
                    "failed": sum(1 for r in results if not r.get("success")),
                    "total_alerts": sum(len(r.get("alerts", [])) for r in results),
                }

            except Exception as e:
                logger.error(f"poll_all_devices failed: {e}")
                await db.rollback()
                return {"status": "error", "error": str(e)}

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
