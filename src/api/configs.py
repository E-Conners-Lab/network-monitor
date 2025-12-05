"""Configuration backup API endpoints."""

import difflib
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.models.base import get_db
from src.models.config_backup import ConfigBackup
from src.models.device import Device
from src.models.user import User
from src.schemas.config_backup import (
    BackupTriggerRequest,
    BackupTriggerResponse,
    ConfigBackupDetail,
    ConfigBackupSummary,
    ConfigDiffResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ConfigBackupSummary])
async def list_config_backups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    device_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List config backups with optional device filter."""
    query = select(ConfigBackup).order_by(desc(ConfigBackup.created_at))

    if device_id:
        query = query.where(ConfigBackup.device_id == device_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/device/{device_id}", response_model=list[ConfigBackupSummary])
async def list_device_backups(
    device_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all config backups for a specific device."""
    # Verify device exists
    device_result = await db.execute(select(Device).where(Device.id == device_id))
    device = device_result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    query = (
        select(ConfigBackup)
        .where(ConfigBackup.device_id == device_id)
        .order_by(desc(ConfigBackup.created_at))
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/device/{device_id}/latest", response_model=ConfigBackupDetail | None)
async def get_latest_backup(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the most recent config backup for a device."""
    query = (
        select(ConfigBackup)
        .where(ConfigBackup.device_id == device_id)
        .order_by(desc(ConfigBackup.created_at))
        .limit(1)
    )
    result = await db.execute(query)
    backup = result.scalar_one_or_none()

    if not backup:
        return None

    return backup


# NOTE: This route MUST come BEFORE /{backup_id} to avoid matching issues
@router.get("/diff/{backup_id_1}/{backup_id_2}", response_model=ConfigDiffResponse)
async def compare_configs(
    backup_id_1: int,
    backup_id_2: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare two config backups and return a unified diff."""
    # Fetch both backups
    result1 = await db.execute(
        select(ConfigBackup).where(ConfigBackup.id == backup_id_1)
    )
    backup1 = result1.scalar_one_or_none()

    result2 = await db.execute(
        select(ConfigBackup).where(ConfigBackup.id == backup_id_2)
    )
    backup2 = result2.scalar_one_or_none()

    if not backup1:
        raise HTTPException(status_code=404, detail=f"Backup {backup_id_1} not found")
    if not backup2:
        raise HTTPException(status_code=404, detail=f"Backup {backup_id_2} not found")

    # Ensure both are from same device
    if backup1.device_id != backup2.device_id:
        raise HTTPException(
            status_code=400,
            detail="Can only compare configs from the same device"
        )

    # Generate diff
    lines1 = backup1.config_text.splitlines(keepends=True)
    lines2 = backup2.config_text.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        lines1,
        lines2,
        fromfile=f"backup_{backup_id_1} ({backup1.created_at.isoformat()})",
        tofile=f"backup_{backup_id_2} ({backup2.created_at.isoformat()})",
        lineterm=""
    ))

    diff_text = "\n".join(diff)
    has_changes = backup1.config_hash != backup2.config_hash

    # Count changes
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return ConfigDiffResponse(
        backup_1=ConfigBackupSummary(
            id=backup1.id,
            device_id=backup1.device_id,
            config_type=backup1.config_type,
            config_hash=backup1.config_hash,
            config_size=backup1.config_size,
            line_count=backup1.line_count,
            triggered_by=backup1.triggered_by,
            created_at=backup1.created_at,
        ),
        backup_2=ConfigBackupSummary(
            id=backup2.id,
            device_id=backup2.device_id,
            config_type=backup2.config_type,
            config_hash=backup2.config_hash,
            config_size=backup2.config_size,
            line_count=backup2.line_count,
            triggered_by=backup2.triggered_by,
            created_at=backup2.created_at,
        ),
        has_changes=has_changes,
        added_lines=added,
        removed_lines=removed,
        diff_text=diff_text,
    )


@router.post("/backup", response_model=BackupTriggerResponse)
async def trigger_backup(
    request: BackupTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a config backup for specified devices or all devices."""
    from src.tasks.config_backup import backup_device_configs

    # Get device count
    if request.device_ids:
        query = select(Device).where(
            Device.id.in_(request.device_ids),
            Device.is_active == True  # noqa: E712
        )
    else:
        query = select(Device).where(Device.is_active == True)  # noqa: E712

    result = await db.execute(query)
    devices = result.scalars().all()

    if not devices:
        raise HTTPException(status_code=404, detail="No active devices found")

    device_ids = [d.id for d in devices]

    # Trigger async backup task
    task = backup_device_configs.delay(
        device_ids=device_ids,
        config_type=request.config_type,
        triggered_by=request.triggered_by or current_user.username,
    )

    return BackupTriggerResponse(
        task_id=task.id,
        message=f"Backup triggered for {len(devices)} devices",
        device_count=len(devices),
    )


# NOTE: This route MUST come AFTER more specific routes like /diff/...
@router.get("/{backup_id}", response_model=ConfigBackupDetail)
async def get_config_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific config backup by ID (includes full config text)."""
    result = await db.execute(
        select(ConfigBackup).where(ConfigBackup.id == backup_id)
    )
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(status_code=404, detail="Config backup not found")

    return backup


@router.delete("/{backup_id}")
async def delete_config_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific config backup."""
    result = await db.execute(
        select(ConfigBackup).where(ConfigBackup.id == backup_id)
    )
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(status_code=404, detail="Config backup not found")

    await db.delete(backup)
    await db.commit()

    return {"message": f"Backup {backup_id} deleted"}
