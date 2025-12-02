"""Metric model for storing device metrics."""

import enum
from typing import Optional

from sqlalchemy import String, Float, ForeignKey, Enum, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class MetricType(enum.Enum):
    """Types of metrics collected."""

    # System metrics
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    UPTIME = "uptime"

    # Interface metrics
    INTERFACE_STATUS = "interface_status"
    INTERFACE_IN_OCTETS = "interface_in_octets"
    INTERFACE_OUT_OCTETS = "interface_out_octets"
    INTERFACE_IN_ERRORS = "interface_in_errors"
    INTERFACE_OUT_ERRORS = "interface_out_errors"
    INTERFACE_IN_RATE = "interface_in_rate"  # bits per second
    INTERFACE_OUT_RATE = "interface_out_rate"  # bits per second

    # Routing metrics
    BGP_NEIGHBOR_STATE = "bgp_neighbor_state"
    OSPF_NEIGHBOR_STATE = "ospf_neighbor_state"

    # Firewall metrics (ASA)
    CONNECTION_COUNT = "connection_count"
    FAILOVER_STATUS = "failover_status"

    # Reachability
    PING_LATENCY = "ping_latency"
    PING_LOSS = "ping_loss"

    # Custom
    CUSTOM = "custom"


class Metric(Base):
    """Time-series metric data for devices."""

    __tablename__ = "metrics"

    # Foreign key
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)

    # Metric info
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType))
    metric_name: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Context (e.g., interface name, BGP peer)
    context: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="metrics")

    # Indexes for efficient time-series queries
    __table_args__ = (
        Index("ix_metrics_device_type_created", "device_id", "metric_type", "created_at"),
        Index("ix_metrics_device_created", "device_id", "created_at"),
        Index("ix_metrics_device_context", "device_id", "metric_type", "context"),
    )

    def __repr__(self) -> str:
        return f"<Metric(device_id={self.device_id}, type={self.metric_type.value}, value={self.value})>"


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.device import Device
