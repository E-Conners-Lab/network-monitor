"""Metrics API endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import get_db
from src.models.metric import Metric, MetricType
from src.schemas.metric import MetricCreate, MetricResponse, MetricSummary
from src.api.auth import get_current_user
from src.models.user import User

router = APIRouter()


@router.get("", response_model=list[MetricResponse])
async def list_metrics(
    device_id: Optional[int] = None,
    metric_type: Optional[MetricType] = None,
    hours: int = Query(24, ge=1, le=168),  # Max 1 week
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List metrics with optional filtering."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = select(Metric).where(Metric.created_at >= cutoff)

    if device_id:
        query = query.where(Metric.device_id == device_id)
    if metric_type:
        query = query.where(Metric.metric_type == metric_type)

    query = query.order_by(Metric.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/device/{device_id}", response_model=list[MetricResponse])
async def get_device_metrics(
    device_id: int,
    metric_type: Optional[MetricType] = None,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all metrics for a specific device."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = select(Metric).where(
        Metric.device_id == device_id, Metric.created_at >= cutoff
    )

    if metric_type:
        query = query.where(Metric.metric_type == metric_type)

    query = query.order_by(Metric.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/device/{device_id}/latest", response_model=dict)
async def get_device_latest_metrics(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the latest metrics for each type for a device."""
    # Get distinct metric types for this device
    types_query = select(Metric.metric_type).where(Metric.device_id == device_id).distinct()
    types_result = await db.execute(types_query)
    metric_types = types_result.scalars().all()

    latest_metrics = {}
    for mt in metric_types:
        query = (
            select(Metric)
            .where(Metric.device_id == device_id, Metric.metric_type == mt)
            .order_by(Metric.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        metric = result.scalar_one_or_none()
        if metric:
            latest_metrics[mt.value] = {
                "value": metric.value,
                "unit": metric.unit,
                "context": metric.context,
                "timestamp": metric.created_at.isoformat(),
            }

    return {"device_id": device_id, "metrics": latest_metrics}


@router.get("/device/{device_id}/summary", response_model=list[MetricSummary])
async def get_device_metrics_summary(
    device_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get metric summaries (min, max, avg) for a device."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # Get summary stats grouped by metric type
    query = (
        select(
            Metric.metric_type,
            func.min(Metric.value).label("min_value"),
            func.max(Metric.value).label("max_value"),
            func.avg(Metric.value).label("avg_value"),
            func.count(Metric.id).label("count"),
        )
        .where(Metric.device_id == device_id, Metric.created_at >= cutoff)
        .group_by(Metric.metric_type)
    )
    result = await db.execute(query)
    summaries = []

    for row in result:
        # Get latest value for this metric type
        latest_query = (
            select(Metric)
            .where(Metric.device_id == device_id, Metric.metric_type == row.metric_type)
            .order_by(Metric.created_at.desc())
            .limit(1)
        )
        latest_result = await db.execute(latest_query)
        latest = latest_result.scalar_one_or_none()

        summaries.append(
            MetricSummary(
                device_id=device_id,
                metric_type=row.metric_type,
                min_value=row.min_value,
                max_value=row.max_value,
                avg_value=row.avg_value,
                count=row.count,
                latest_value=latest.value if latest else 0,
                latest_timestamp=latest.created_at if latest else datetime.utcnow(),
            )
        )

    return summaries


@router.post("", response_model=MetricResponse, status_code=201)
async def create_metric(
    metric_data: MetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new metric (typically done by monitoring system)."""
    metric = Metric(**metric_data.model_dump())
    db.add(metric)
    await db.flush()
    await db.refresh(metric)
    return metric
