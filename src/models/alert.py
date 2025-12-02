"""Alert model for device alerts."""

import enum
from typing import Optional
from datetime import datetime

from sqlalchemy import String, ForeignKey, Enum, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class AlertSeverity(enum.Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(enum.Enum):
    """Alert status."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(Base):
    """Alert model for device alerts and notifications."""

    __tablename__ = "alerts"

    # Foreign key
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)

    # Alert info
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity))
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.ACTIVE)

    # Context
    alert_type: Mapped[str] = mapped_column(String(50))  # e.g., "high_cpu", "interface_down"
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Resolution
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notification tracking
    webhook_sent: Mapped[bool] = mapped_column(default=False)
    webhook_sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="alerts")

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_alerts_device_status", "device_id", "status"),
        Index("ix_alerts_device_severity", "device_id", "severity"),
        Index("ix_alerts_status_severity", "status", "severity"),
    )

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, device_id={self.device_id}, severity={self.severity.value})>"


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.device import Device
