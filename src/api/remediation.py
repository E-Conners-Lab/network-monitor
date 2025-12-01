"""Remediation API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import get_db
from src.models.device import Device
from src.models.alert import Alert, AlertStatus
from src.models.remediation_log import RemediationLog, RemediationStatus
from src.api.auth import get_current_user
from src.models.user import User
from src.tasks.remediation import (
    execute_remediation,
    interface_enable,
    clear_bgp_session,
    clear_device_caches,
    send_webhook_alert,
    auto_remediate_alert,
)

router = APIRouter()


# Request/Response models
class RemediationRequest(BaseModel):
    """Request to execute a remediation playbook."""

    playbook_name: str
    alert_id: Optional[int] = None


class InterfaceEnableRequest(BaseModel):
    """Request to enable an interface."""

    interface_name: str


class ClearBGPRequest(BaseModel):
    """Request to clear a BGP session."""

    neighbor_ip: str


class RemediationResponse(BaseModel):
    """Response for a remediation request."""

    task_id: str
    status: str
    message: str


class RemediationLogResponse(BaseModel):
    """Response model for remediation log entries."""

    id: int
    device_id: int
    alert_id: Optional[int]
    playbook_name: str
    action_type: str
    status: RemediationStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    commands_executed: Optional[list]
    error_message: Optional[str]
    attempt_number: int
    created_at: datetime

    class Config:
        from_attributes = True


# Available playbooks
AVAILABLE_PLAYBOOKS = {
    "clear_arp_cache": "Clear ARP cache on the device",
    "clear_ip_route_cache": "Clear IP routing cache",
    "save_config": "Save running config to startup",
    "clear_conn": "Clear all connections (ASA only)",
    "clear_xlate": "Clear NAT translations (ASA only)",
}


@router.get("/playbooks")
async def list_playbooks(
    current_user: User = Depends(get_current_user),
):
    """List available remediation playbooks."""
    return [
        {"name": name, "description": desc}
        for name, desc in AVAILABLE_PLAYBOOKS.items()
    ]


@router.get("/logs", response_model=list[RemediationLogResponse])
async def list_remediation_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    device_id: Optional[int] = None,
    status: Optional[RemediationStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List remediation logs with optional filtering."""
    query = select(RemediationLog).order_by(RemediationLog.created_at.desc())

    if device_id:
        query = query.where(RemediationLog.device_id == device_id)
    if status:
        query = query.where(RemediationLog.status == status)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/logs/{log_id}", response_model=RemediationLogResponse)
async def get_remediation_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific remediation log by ID."""
    result = await db.execute(
        select(RemediationLog).where(RemediationLog.id == log_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Remediation log not found")

    return log


@router.post("/devices/{device_id}/execute", response_model=RemediationResponse)
async def execute_playbook(
    device_id: int,
    request: RemediationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a remediation playbook on a device."""
    # Verify device exists
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Verify playbook exists
    if request.playbook_name not in AVAILABLE_PLAYBOOKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown playbook: {request.playbook_name}. Available: {list(AVAILABLE_PLAYBOOKS.keys())}",
        )

    # Queue the remediation task
    task = execute_remediation.delay(
        device_id=device_id,
        playbook_name=request.playbook_name,
        alert_id=request.alert_id,
    )

    return RemediationResponse(
        task_id=task.id,
        status="queued",
        message=f"Remediation playbook '{request.playbook_name}' queued for device {device.name}",
    )


@router.post("/devices/{device_id}/interface/enable", response_model=RemediationResponse)
async def enable_interface(
    device_id: int,
    request: InterfaceEnableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable a disabled interface on a device."""
    # Verify device exists
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Queue the interface enable task
    task = interface_enable.delay(
        device_id=device_id,
        interface_name=request.interface_name,
    )

    return RemediationResponse(
        task_id=task.id,
        status="queued",
        message=f"Interface enable queued for {request.interface_name} on {device.name}",
    )


@router.post("/devices/{device_id}/bgp/clear", response_model=RemediationResponse)
async def clear_bgp(
    device_id: int,
    request: ClearBGPRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear a BGP session on a device."""
    # Verify device exists
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Queue the BGP clear task
    task = clear_bgp_session.delay(
        device_id=device_id,
        neighbor_ip=request.neighbor_ip,
    )

    return RemediationResponse(
        task_id=task.id,
        status="queued",
        message=f"BGP session clear queued for neighbor {request.neighbor_ip} on {device.name}",
    )


@router.post("/devices/{device_id}/caches/clear", response_model=RemediationResponse)
async def clear_caches(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear caches on a device to free memory."""
    # Verify device exists
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Queue the cache clear task
    task = clear_device_caches.delay(device_id=device_id)

    return RemediationResponse(
        task_id=task.id,
        status="queued",
        message=f"Cache clear queued for device {device.name}",
    )


@router.post("/alerts/{alert_id}/auto-remediate", response_model=RemediationResponse)
async def trigger_auto_remediation(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger automatic remediation for an alert based on its type."""
    # Verify alert exists
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != AlertStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Alert is not active")

    # Queue the auto-remediation task
    task = auto_remediate_alert.delay(alert_id=alert_id)

    return RemediationResponse(
        task_id=task.id,
        status="queued",
        message=f"Auto-remediation queued for alert {alert_id}",
    )


@router.post("/alerts/{alert_id}/send-webhook", response_model=RemediationResponse)
async def trigger_webhook(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a webhook notification for an alert."""
    # Verify alert exists
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Queue the webhook task
    task = send_webhook_alert.delay(alert_id=alert_id)

    return RemediationResponse(
        task_id=task.id,
        status="queued",
        message=f"Webhook notification queued for alert {alert_id}",
    )
