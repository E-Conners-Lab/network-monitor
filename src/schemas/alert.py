"""Alert schemas."""

from datetime import datetime

from pydantic import BaseModel

from src.models.alert import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    """Schema for creating a new alert."""

    device_id: int
    title: str
    message: str
    severity: AlertSeverity
    alert_type: str
    context: dict | None = None


class AlertUpdate(BaseModel):
    """Schema for updating an alert."""

    status: AlertStatus | None = None
    acknowledged_by: str | None = None
    resolution_notes: str | None = None


class AlertResponse(BaseModel):
    """Schema for alert response."""

    id: int
    device_id: int
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    alert_type: str
    context: dict | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolution_notes: str | None
    webhook_sent: bool
    webhook_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
