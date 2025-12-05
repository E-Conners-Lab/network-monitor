"""Remediation log model for tracking automated fixes."""

import enum
from datetime import datetime

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class RemediationStatus(enum.Enum):
    """Status of a remediation action."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RemediationLog(Base):
    """Log of automated remediation actions."""

    __tablename__ = "remediation_logs"

    # Foreign keys
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("alerts.id"), nullable=True, index=True
    )

    # Remediation info
    playbook_name: Mapped[str] = mapped_column(String(100))
    action_type: Mapped[str] = mapped_column(String(50))  # e.g., "interface_enable", "clear_bgp"
    status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus), default=RemediationStatus.PENDING
    )

    # Execution details
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # State capture
    state_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Commands and output
    commands_executed: Mapped[list | None] = mapped_column(JSON, nullable=True)
    command_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry tracking
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="remediation_logs")

    def __repr__(self) -> str:
        return f"<RemediationLog(id={self.id}, playbook={self.playbook_name}, status={self.status.value})>"


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.device import Device
