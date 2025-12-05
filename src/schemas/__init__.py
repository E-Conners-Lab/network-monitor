"""Pydantic schemas for API request/response models."""

from src.schemas.alert import AlertCreate, AlertResponse, AlertUpdate
from src.schemas.config_backup import (
    BackupTriggerRequest,
    BackupTriggerResponse,
    ConfigBackupDetail,
    ConfigBackupResponse,
    ConfigBackupSummary,
    ConfigDiffRequest,
    ConfigDiffResponse,
)
from src.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate
from src.schemas.metric import MetricCreate, MetricResponse
from src.schemas.user import Token, TokenData, UserCreate, UserLogin, UserResponse

__all__ = [
    "UserCreate",
    "UserResponse",
    "UserLogin",
    "Token",
    "TokenData",
    "DeviceCreate",
    "DeviceUpdate",
    "DeviceResponse",
    "AlertCreate",
    "AlertUpdate",
    "AlertResponse",
    "MetricCreate",
    "MetricResponse",
    "ConfigBackupResponse",
    "ConfigBackupSummary",
    "ConfigBackupDetail",
    "ConfigDiffRequest",
    "ConfigDiffResponse",
    "BackupTriggerRequest",
    "BackupTriggerResponse",
]
