"""Device API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import get_db
from src.models.device import Device, DeviceType
from src.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse
from src.api.auth import get_current_user
from src.models.user import User
from src.core.health_checks import check_device_connectivity, HealthCheckService
from src.drivers.base import DevicePlatform
from src.integrations.netbox import NetBoxClient, NetBoxSyncService
from src.tasks.polling import poll_all_devices

router = APIRouter()


# Request/Response models for connectivity checks
class ConnectivityCheckRequest(BaseModel):
    """Request body for connectivity check with credentials."""

    username: Optional[str] = None
    password: Optional[str] = None
    enable_password: Optional[str] = None
    snmp_community: str = "public"
    check_ping: bool = True
    check_snmp: bool = True
    check_ssh: bool = True


class ConnectivityCheckResponse(BaseModel):
    """Response for connectivity check."""

    device_id: int
    device_name: str
    ip_address: str
    timestamp: datetime
    ping: Optional[dict] = None
    snmp: Optional[dict] = None
    ssh: Optional[dict] = None
    overall_reachable: bool


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    device_type: Optional[DeviceType] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all devices with optional filtering."""
    query = select(Device)

    if device_type:
        query = query.where(Device.device_type == device_type)
    if is_active is not None:
        query = query.where(Device.is_active == is_active)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific device by ID."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device


@router.post("", response_model=DeviceResponse, status_code=201)
async def create_device(
    device_data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new device."""
    # Check for duplicate name
    result = await db.execute(select(Device).where(Device.name == device_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Device with this name already exists")

    device = Device(**device_data.model_dump())
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    device_data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a device."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    update_data = device_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.flush()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a device."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    await db.delete(device)


@router.post("/{device_id}/check", response_model=ConnectivityCheckResponse)
async def check_device_connectivity_endpoint(
    device_id: int,
    check_request: ConnectivityCheckRequest = Body(default=ConnectivityCheckRequest()),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check device connectivity (ping, SNMP, SSH).

    Provide credentials in the request body to test SSH connectivity.
    SNMP community string defaults to 'public'.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Map device type to platform
    platform_map = {
        DeviceType.ROUTER: DevicePlatform.CISCO_IOS,
        DeviceType.SWITCH: DevicePlatform.CISCO_IOS,
        DeviceType.FIREWALL: DevicePlatform.CISCO_ASA,
    }
    platform = platform_map.get(device.device_type, DevicePlatform.CISCO_IOS)

    # Run connectivity checks
    check_result = await check_device_connectivity(
        device_id=device.id,
        device_name=device.name,
        ip_address=device.ip_address,
        username=check_request.username,
        password=check_request.password,
        enable_password=check_request.enable_password,
        snmp_community=check_request.snmp_community or device.snmp_community or "public",
        platform=platform,
        check_ping=check_request.check_ping,
        check_snmp=check_request.check_snmp,
        check_ssh=check_request.check_ssh,
    )

    # Update device reachability status
    device.is_reachable = check_result.overall_reachable
    device.last_seen = datetime.utcnow().isoformat() if check_result.overall_reachable else device.last_seen

    # Update OS version if SSH check was successful and returned version info
    if check_result.ssh and check_result.ssh.get("success") and check_result.ssh.get("os_version"):
        device.os_version = check_result.ssh.get("os_version")

    await db.flush()

    return ConnectivityCheckResponse(
        device_id=check_result.device_id,
        device_name=check_result.device_name,
        ip_address=check_result.ip_address,
        timestamp=check_result.timestamp,
        ping={
            "success": check_result.ping.success,
            "latency_ms": check_result.ping.latency_ms,
            "packet_loss": check_result.ping.packet_loss,
            "error": check_result.ping.error,
        } if check_result.ping else None,
        snmp=check_result.snmp,
        ssh=check_result.ssh,
        overall_reachable=check_result.overall_reachable,
    )


class CheckAllResponse(BaseModel):
    """Response for check-all endpoint."""
    task_id: str
    status: str
    message: str


@router.post("/check-all", response_model=CheckAllResponse)
async def check_all_devices_connectivity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger connectivity/metric polling for all active devices.

    This queues a background task and returns immediately.
    Results will be visible in device status and metrics.
    """
    result = await db.execute(select(Device).where(Device.is_active == True))
    devices = result.scalars().all()

    if not devices:
        return CheckAllResponse(
            task_id="",
            status="skipped",
            message="No active devices to check"
        )

    # Queue the polling task - returns immediately
    task = poll_all_devices.delay()

    return CheckAllResponse(
        task_id=task.id,
        status="queued",
        message=f"Polling task queued for {len(devices)} devices"
    )


# NetBox sync endpoints

@router.get("/netbox/status")
async def netbox_status(
    current_user: User = Depends(get_current_user),
):
    """Check NetBox connection status."""
    client = NetBoxClient()
    return client.test_connection()


@router.post("/netbox/sync")
async def sync_from_netbox(
    site: Optional[str] = Query(None, description="Filter devices by NetBox site"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync devices from NetBox.

    Creates new devices and updates existing ones based on NetBox data.
    Devices are matched by netbox_id or name.
    """
    sync_service = NetBoxSyncService()
    result = await sync_service.sync_devices(db, site=site)
    return result


@router.get("/netbox/devices")
async def list_netbox_devices(
    site: Optional[str] = Query(None, description="Filter by site"),
    role: Optional[str] = Query(None, description="Filter by role"),
    current_user: User = Depends(get_current_user),
):
    """List devices from NetBox (preview before sync)."""
    client = NetBoxClient()

    if not client.is_configured:
        raise HTTPException(status_code=400, detail="NetBox not configured (missing token)")

    devices = client.get_devices(site=site, role=role)
    return [
        {
            "netbox_id": d.netbox_id,
            "name": d.name,
            "ip_address": d.ip_address,
            "device_type": d.device_type.value,
            "vendor": d.vendor,
            "model": d.model,
            "site": d.site,
            "status": d.status,
        }
        for d in devices
    ]


class CollectOsVersionsRequest(BaseModel):
    """Request body for collecting OS versions."""
    username: str
    password: str


class CollectOsVersionsResponse(BaseModel):
    """Response for OS version collection."""
    updated: int
    failed: int
    results: list[dict]


@router.post("/collect-os-versions", response_model=CollectOsVersionsResponse)
async def collect_os_versions(
    request: CollectOsVersionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Collect OS versions from all active devices via SSH.

    This connects to each device, runs 'show version', and parses the OS version.
    The os_version field is updated for each device.
    """
    from src.core.health_checks import check_ssh, parse_os_version

    result = await db.execute(select(Device).where(Device.is_active == True))
    devices = result.scalars().all()

    results = []
    updated = 0
    failed = 0

    for device in devices:
        try:
            # Get credentials from device tags if available, otherwise use provided
            tags = device.tags or {}
            username = tags.get("ssh_username", request.username)
            password = tags.get("ssh_password", request.password)

            # Map device type to platform
            platform_map = {
                DeviceType.ROUTER: DevicePlatform.CISCO_IOS,
                DeviceType.SWITCH: DevicePlatform.CISCO_IOS,
                DeviceType.FIREWALL: DevicePlatform.CISCO_ASA,
            }
            platform = platform_map.get(device.device_type, DevicePlatform.CISCO_IOS)

            ssh_result = check_ssh(
                device.ip_address,
                username,
                password,
                platform,
                port=device.ssh_port or 22,
                timeout=30,
            )

            if ssh_result.get("success") and ssh_result.get("os_version"):
                device.os_version = ssh_result["os_version"]
                updated += 1
                results.append({
                    "device_id": device.id,
                    "name": device.name,
                    "status": "updated",
                    "os_version": ssh_result["os_version"],
                })
            else:
                failed += 1
                results.append({
                    "device_id": device.id,
                    "name": device.name,
                    "status": "failed",
                    "error": ssh_result.get("error", "Could not parse OS version"),
                })

        except Exception as e:
            failed += 1
            results.append({
                "device_id": device.id,
                "name": device.name,
                "status": "error",
                "error": str(e),
            })

    await db.commit()

    return CollectOsVersionsResponse(
        updated=updated,
        failed=failed,
        results=results,
    )


class SyncOsToNetBoxResponse(BaseModel):
    """Response for syncing OS versions to NetBox."""
    updated: int
    failed: int
    skipped: int
    details: list[dict]


@router.post("/sync-os-to-netbox", response_model=SyncOsToNetBoxResponse)
async def sync_os_versions_to_netbox(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync OS versions from local database to NetBox.

    Updates the platform and software_version custom field in NetBox
    for all devices that have a netbox_id and os_version set locally.
    """
    from src.integrations.netbox import NetBoxClient

    # Get all devices with netbox_id and os_version
    result = await db.execute(
        select(Device).where(
            Device.netbox_id.isnot(None),
            Device.os_version.isnot(None),
        )
    )
    devices = result.scalars().all()

    if not devices:
        return SyncOsToNetBoxResponse(
            updated=0,
            failed=0,
            skipped=0,
            details=[{"message": "No devices with netbox_id and os_version found"}],
        )

    # Prepare device data for NetBox update
    device_data = [
        {"netbox_id": d.netbox_id, "os_version": d.os_version, "name": d.name}
        for d in devices
    ]

    # Update NetBox
    client = NetBoxClient()
    if not client.is_configured:
        raise HTTPException(status_code=400, detail="NetBox not configured")

    results = client.update_devices_os_versions(device_data)

    return SyncOsToNetBoxResponse(
        updated=results.get("updated", 0),
        failed=results.get("failed", 0),
        skipped=len(devices) - results.get("updated", 0) - results.get("failed", 0),
        details=results.get("details", []),
    )
