"""Alert API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.models.alert import Alert, AlertSeverity, AlertStatus
from src.models.base import get_db
from src.models.user import User
from src.schemas.alert import AlertCreate, AlertResponse, AlertUpdate

router = APIRouter()


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    device_id: int | None = None,
    severity: AlertSeverity | None = None,
    status: AlertStatus | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all alerts with optional filtering."""
    query = select(Alert).order_by(Alert.created_at.desc())

    if device_id:
        query = query.where(Alert.device_id == device_id)
    if severity:
        query = query.where(Alert.severity == severity)
    if status:
        query = query.where(Alert.status == status)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/active", response_model=list[AlertResponse])
async def list_active_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active (unresolved) alerts."""
    query = (
        select(Alert)
        .where(Alert.status == AlertStatus.ACTIVE)
        .order_by(Alert.severity.desc(), Alert.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific alert by ID."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new alert (typically done by monitoring system)."""
    alert = Alert(**alert_data.model_dump())
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    alert_data: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an alert (acknowledge, resolve, etc.)."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    update_data = alert_data.model_dump(exclude_unset=True)

    # Handle status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == AlertStatus.ACKNOWLEDGED and alert.status == AlertStatus.ACTIVE:
            alert.acknowledged_at = datetime.utcnow()
            if "acknowledged_by" not in update_data:
                alert.acknowledged_by = current_user.username
        elif new_status == AlertStatus.RESOLVED:
            alert.resolved_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(alert, field, value)

    await db.flush()
    await db.refresh(alert)
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != AlertStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Alert is not active")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.username

    await db.flush()
    await db.refresh(alert)
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: int,
    resolution_notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Alert is already resolved")

    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.utcnow()
    if resolution_notes:
        alert.resolution_notes = resolution_notes

    await db.flush()
    await db.refresh(alert)
    return alert
