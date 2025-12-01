"""Alert schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.models.alert import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    """Schema for creating a new alert."""

    device_id: int
    title: str
    message: str
    severity: AlertSeverity
    alert_type: str
    context: Optional[dict] = None


class AlertUpdate(BaseModel):
    """Schema for updating an alert."""

    status: Optional[AlertStatus] = None
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None


class AlertResponse(BaseModel):
    """Schema for alert response."""

    id: int
    device_id: int
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    alert_type: str
    context: Optional[dict]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    webhook_sent: bool
    webhook_sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
