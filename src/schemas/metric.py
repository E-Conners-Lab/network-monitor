"""Metric schemas."""

from datetime import datetime

from pydantic import BaseModel

from src.models.metric import MetricType


class MetricCreate(BaseModel):
    """Schema for creating a new metric."""

    device_id: int
    metric_type: MetricType
    metric_name: str
    value: float
    unit: str | None = None
    context: str | None = None
    metadata_: dict | None = None


class MetricResponse(BaseModel):
    """Schema for metric response."""

    id: int
    device_id: int
    metric_type: MetricType
    metric_name: str
    value: float
    unit: str | None
    context: str | None
    metadata_: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricSummary(BaseModel):
    """Summary of metrics for a device."""

    device_id: int
    metric_type: MetricType
    min_value: float
    max_value: float
    avg_value: float
    count: int
    latest_value: float
    latest_timestamp: datetime
