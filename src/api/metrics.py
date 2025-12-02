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


@router.get("/device/{device_id}/routing")
async def get_device_routing_neighbors(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get BGP and OSPF neighbor states for a device."""
    from sqlalchemy.orm import selectinload

    # Get latest BGP neighbors
    bgp_subquery = (
        select(
            Metric.context,
            func.max(Metric.created_at).label("max_created")
        )
        .where(
            Metric.device_id == device_id,
            Metric.metric_type == MetricType.BGP_NEIGHBOR_STATE,
        )
        .group_by(Metric.context)
        .subquery()
    )

    bgp_query = (
        select(Metric)
        .join(
            bgp_subquery,
            (Metric.context == bgp_subquery.c.context)
            & (Metric.created_at == bgp_subquery.c.max_created)
        )
        .where(
            Metric.device_id == device_id,
            Metric.metric_type == MetricType.BGP_NEIGHBOR_STATE,
        )
    )

    bgp_result = await db.execute(bgp_query)
    bgp_metrics = bgp_result.scalars().all()

    bgp_neighbors = []
    for m in bgp_metrics:
        metadata = m.metadata_ or {}
        bgp_neighbors.append({
            "neighbor": metadata.get("neighbor", "unknown"),
            "state": metadata.get("state", "unknown"),
            "remote_as": metadata.get("remote_as", "N/A"),
            "prefixes_received": metadata.get("prefixes_received", 0),
            "uptime": metadata.get("uptime", "N/A"),
            "vrf": metadata.get("vrf", "default"),
            "is_up": m.value == 1.0,
            "timestamp": m.created_at.isoformat(),
        })

    # Get latest OSPF neighbors
    ospf_subquery = (
        select(
            Metric.context,
            func.max(Metric.created_at).label("max_created")
        )
        .where(
            Metric.device_id == device_id,
            Metric.metric_type == MetricType.OSPF_NEIGHBOR_STATE,
        )
        .group_by(Metric.context)
        .subquery()
    )

    ospf_query = (
        select(Metric)
        .join(
            ospf_subquery,
            (Metric.context == ospf_subquery.c.context)
            & (Metric.created_at == ospf_subquery.c.max_created)
        )
        .where(
            Metric.device_id == device_id,
            Metric.metric_type == MetricType.OSPF_NEIGHBOR_STATE,
        )
    )

    ospf_result = await db.execute(ospf_query)
    ospf_metrics = ospf_result.scalars().all()

    ospf_neighbors = []
    for m in ospf_metrics:
        metadata = m.metadata_ or {}
        ospf_neighbors.append({
            "neighbor_id": metadata.get("neighbor_id", "unknown"),
            "state": metadata.get("state", "unknown"),
            "interface": metadata.get("interface", "unknown"),
            "address": metadata.get("address", "N/A"),
            "is_up": m.value == 1.0,
            "timestamp": m.created_at.isoformat(),
        })

    # Count up/down neighbors
    bgp_up = sum(1 for n in bgp_neighbors if n["is_up"])
    bgp_down = len(bgp_neighbors) - bgp_up
    ospf_up = sum(1 for n in ospf_neighbors if n["is_up"])
    ospf_down = len(ospf_neighbors) - ospf_up

    return {
        "device_id": device_id,
        "bgp": {
            "neighbors": bgp_neighbors,
            "total": len(bgp_neighbors),
            "up": bgp_up,
            "down": bgp_down,
        },
        "ospf": {
            "neighbors": ospf_neighbors,
            "total": len(ospf_neighbors),
            "up": ospf_up,
            "down": ospf_down,
        },
    }
