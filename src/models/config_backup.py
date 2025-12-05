"""Configuration backup model for storing device configs."""

import hashlib

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class ConfigBackup(Base):
    """Configuration backup for a network device."""

    __tablename__ = "config_backups"

    # Foreign key to device
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )

    # Config content
    config_type: Mapped[str] = mapped_column(
        String(50), default="running"
    )  # running, startup
    config_text: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA256

    # Metadata
    config_size: Mapped[int] = mapped_column(Integer)  # bytes
    line_count: Mapped[int] = mapped_column(Integer)
    collection_method: Mapped[str] = mapped_column(
        String(50), default="netmiko"
    )  # netmiko, napalm, etc.

    # Optional: who/what triggered the backup
    triggered_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="config_backups")

    def __repr__(self) -> str:
        return f"<ConfigBackup(id={self.id}, device_id={self.device_id}, hash={self.config_hash[:8]}...)>"

    @staticmethod
    def compute_hash(config_text: str) -> str:
        """Compute SHA256 hash of config text."""
        return hashlib.sha256(config_text.encode()).hexdigest()

    @staticmethod
    def has_changed(old_hash: str, new_config: str) -> bool:
        """Check if config has changed by comparing hashes."""
        new_hash = ConfigBackup.compute_hash(new_config)
        return old_hash != new_hash


# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.device import Device