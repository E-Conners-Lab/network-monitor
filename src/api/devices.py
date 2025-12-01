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


@router.post("/check-all", response_model=list[ConnectivityCheckResponse])
async def check_all_devices_connectivity(
    check_request: ConnectivityCheckRequest = Body(default=ConnectivityCheckRequest()),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check connectivity for all active devices.

    Note: This can take a while for many devices. Consider using async task for production.
    """
    result = await db.execute(select(Device).where(Device.is_active == True))
    devices = result.scalars().all()

    if not devices:
        return []

    health_service = HealthCheckService()
    device_configs = [
        {
            "device_id": d.id,
            "device_name": d.name,
            "ip_address": d.ip_address,
            "username": check_request.username,
            "password": check_request.password,
            "snmp_community": check_request.snmp_community or d.snmp_community or "public",
            "check_ping": check_request.check_ping,
            "check_snmp": check_request.check_snmp,
            "check_ssh": check_request.check_ssh,
        }
        for d in devices
    ]

    results = await health_service.check_devices(device_configs, max_concurrent=5)

    # Update device statuses
    for check_result in results:
        device = next((d for d in devices if d.id == check_result.device_id), None)
        if device:
            device.is_reachable = check_result.overall_reachable
            if check_result.overall_reachable:
                device.last_seen = datetime.utcnow().isoformat()

    await db.flush()

    return [
        ConnectivityCheckResponse(
            device_id=r.device_id,
            device_name=r.device_name,
            ip_address=r.ip_address,
            timestamp=r.timestamp,
            ping={
                "success": r.ping.success,
                "latency_ms": r.ping.latency_ms,
                "packet_loss": r.ping.packet_loss,
                "error": r.ping.error,
            } if r.ping else None,
            snmp=r.snmp,
            ssh=r.ssh,
            overall_reachable=r.overall_reachable,
        )
        for r in results
    ]


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
