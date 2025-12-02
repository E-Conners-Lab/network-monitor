"""Metrics API endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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


# Map frontend metric names to enum values
METRIC_TYPE_MAP = {
    "cpu_utilization": MetricType.CPU_UTILIZATION,
    "memory_utilization": MetricType.MEMORY_UTILIZATION,
    "ping_latency": MetricType.PING_LATENCY,
    "ping_loss": MetricType.PING_LOSS,
    "interface_status": MetricType.INTERFACE_STATUS,
    "interface_in_rate": MetricType.INTERFACE_IN_RATE,
    "interface_out_rate": MetricType.INTERFACE_OUT_RATE,
    "bgp_neighbor_state": MetricType.BGP_NEIGHBOR_STATE,
    "ospf_neighbor_state": MetricType.OSPF_NEIGHBOR_STATE,
}


@router.get("/history", response_model=list[MetricResponse])
async def get_metrics_history(
    device_id: int,
    metric_type: str,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get metric history for a specific device and metric type.

    This endpoint is used by the frontend Metrics dashboard to plot charts.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    enum_type = METRIC_TYPE_MAP.get(metric_type.lower())
    if not enum_type:
        return []

    query = (
        select(Metric)
        .where(
            Metric.device_id == device_id,
            Metric.metric_type == enum_type,
            Metric.created_at >= cutoff
        )
        .order_by(Metric.created_at.asc())  # Ascending for charts
        .limit(1000)  # Limit data points for performance
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/history/batch", response_model=dict)
async def get_metrics_history_batch(
    device_id: int,
    metric_types: str = Query(..., description="Comma-separated list of metric types"),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get metric history for multiple metric types in a single request.

    This batch endpoint reduces N API calls to 1 for the Metrics dashboard.
    Returns a dict with metric_type as key and list of metrics as value.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    requested_types = [t.strip().lower() for t in metric_types.split(",")]

    # Map to enum types
    enum_types = []
    for mt in requested_types:
        if mt in METRIC_TYPE_MAP:
            enum_types.append(METRIC_TYPE_MAP[mt])

    if not enum_types:
        return {}

    # Single query for all metric types
    query = (
        select(Metric)
        .where(
            Metric.device_id == device_id,
            Metric.metric_type.in_(enum_types),
            Metric.created_at >= cutoff
        )
        .order_by(Metric.metric_type, Metric.created_at.asc())
    )
    result = await db.execute(query)
    metrics = result.scalars().all()

    # Group by metric type
    grouped = {}
    for metric in metrics:
        type_name = metric.metric_type.value
        if type_name not in grouped:
            grouped[type_name] = []
        grouped[type_name].append({
            "id": metric.id,
            "device_id": metric.device_id,
            "metric_type": metric.metric_type,
            "metric_name": metric.metric_name,
            "value": metric.value,
            "unit": metric.unit,
            "context": metric.context,
            "metadata_": metric.metadata_,
            "created_at": metric.created_at,
        })

    return grouped


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
    """Get the latest metrics for each type for a device (optimized single query)."""
    # Use a subquery to get the max created_at per metric_type
    subq = (
        select(
            Metric.metric_type,
            func.max(Metric.created_at).label("max_created")
        )
        .where(Metric.device_id == device_id)
        .group_by(Metric.metric_type)
        .subquery()
    )

    # Join to get the full metric rows for each latest
    query = (
        select(Metric)
        .join(
            subq,
            and_(
                Metric.device_id == device_id,
                Metric.metric_type == subq.c.metric_type,
                Metric.created_at == subq.c.max_created
            )
        )
    )

    result = await db.execute(query)
    metrics = result.scalars().all()

    latest_metrics = {}
    for metric in metrics:
        latest_metrics[metric.metric_type.value] = {
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
    """Get metric summaries (min, max, avg) for a device (optimized single query)."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # Get summary stats grouped by metric type
    summary_query = (
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
    summary_result = await db.execute(summary_query)
    summary_rows = {row.metric_type: row for row in summary_result}

    # Get all latest metrics in a single query
    latest_subq = (
        select(
            Metric.metric_type,
            func.max(Metric.created_at).label("max_created")
        )
        .where(Metric.device_id == device_id)
        .group_by(Metric.metric_type)
        .subquery()
    )

    latest_query = (
        select(Metric)
        .join(
            latest_subq,
            and_(
                Metric.device_id == device_id,
                Metric.metric_type == latest_subq.c.metric_type,
                Metric.created_at == latest_subq.c.max_created
            )
        )
    )
    latest_result = await db.execute(latest_query)
    latest_metrics = {m.metric_type: m for m in latest_result.scalars().all()}

    # Combine results
    summaries = []
    for metric_type, row in summary_rows.items():
        latest = latest_metrics.get(metric_type)
        summaries.append(
            MetricSummary(
                device_id=device_id,
                metric_type=metric_type,
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
