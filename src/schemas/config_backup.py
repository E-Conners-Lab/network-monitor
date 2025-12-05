"""Schemas for configuration backup operations."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConfigBackupBase(BaseModel):
    """Base schema for config backup."""

    config_type: str = Field(default="running", description="Type of config: running, startup")


class ConfigBackupCreate(ConfigBackupBase):
    """Schema for creating a config backup."""

    device_id: int
    config_text: str
    triggered_by: str | None = None


class ConfigBackupResponse(ConfigBackupBase):
    """Schema for config backup response."""

    id: int
    device_id: int
    config_hash: str
    config_size: int
    line_count: int
    collection_method: str
    triggered_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ConfigBackupSummary(BaseModel):
    """Summary of a config backup without full text."""

    id: int
    device_id: int
    config_type: str
    config_hash: str
    config_size: int
    line_count: int
    triggered_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ConfigBackupDetail(ConfigBackupResponse):
    """Full config backup with text content."""

    config_text: str

    class Config:
        from_attributes = True


class ConfigDiffRequest(BaseModel):
    """Request for config diff."""

    backup_id_1: int = Field(description="First backup ID (older)")
    backup_id_2: int = Field(description="Second backup ID (newer)")


class ConfigDiffLine(BaseModel):
    """Single line in a diff."""

    line_number: int
    content: str
    change_type: str = Field(description="added, removed, or unchanged")


class ConfigDiffResponse(BaseModel):
    """Response for config diff."""

    backup_1: ConfigBackupSummary
    backup_2: ConfigBackupSummary
    has_changes: bool
    added_lines: int
    removed_lines: int
    diff_text: str  # Unified diff format
    diff_lines: list[ConfigDiffLine] | None = None


class BackupTriggerRequest(BaseModel):
    """Request to trigger a backup."""

    device_ids: list[int] | None = Field(
        default=None, description="Specific device IDs to backup. None = all devices"
    )
    config_type: str = Field(default="running", description="running or startup")
    triggered_by: str = Field(default="manual", description="Who/what triggered this backup")


class BackupTriggerResponse(BaseModel):
    """Response from backup trigger."""

    task_id: str
    message: str
    device_count: int
