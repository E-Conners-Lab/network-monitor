"""Device model for network devices."""

import enum

from sqlalchemy import JSON, Boolean, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class DeviceType(enum.Enum):
    """Supported device types."""

    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    ACCESS_POINT = "access_point"
    OTHER = "other"


class Device(Base):
    """Network device model."""

    __tablename__ = "devices"

    # Basic info
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[str] = mapped_column(String(45), index=True)  # IPv6 max length
    device_type: Mapped[DeviceType] = mapped_column(Enum(DeviceType))
    vendor: Mapped[str] = mapped_column(String(50), default="cisco")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Connection settings
    snmp_community: Mapped[str | None] = mapped_column(String(100), nullable=True)
    snmp_version: Mapped[int] = mapped_column(Integer, default=2)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    netconf_port: Mapped[int] = mapped_column(Integer, default=830)

    # NetBox integration
    netbox_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Additional data
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    metrics: Mapped[list["Metric"]] = relationship(
        "Metric", back_populates="device", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="device", cascade="all, delete-orphan"
    )
    remediation_logs: Mapped[list["RemediationLog"]] = relationship(
        "RemediationLog", back_populates="device", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, name={self.name}, ip={self.ip_address})>"


# Import for type hints (avoid circular imports)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.alert import Alert
    from src.models.metric import Metric
    from src.models.remediation_log import RemediationLog
