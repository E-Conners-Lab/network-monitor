"""Device schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, IPvAnyAddress

from src.models.device import DeviceType


class DeviceCreate(BaseModel):
    """Schema for creating a new device."""

    name: str
    hostname: str
    ip_address: str
    device_type: DeviceType
    vendor: str = "cisco"
    model: Optional[str] = None
    os_version: Optional[str] = None
    snmp_community: Optional[str] = None
    snmp_version: int = 2
    ssh_port: int = 22
    netconf_port: int = 830
    netbox_id: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[dict] = None


class DeviceUpdate(BaseModel):
    """Schema for updating a device."""

    name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    device_type: Optional[DeviceType] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    is_active: Optional[bool] = None
    snmp_community: Optional[str] = None
    snmp_version: Optional[int] = None
    ssh_port: Optional[int] = None
    netconf_port: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[dict] = None


class DeviceResponse(BaseModel):
    """Schema for device response."""

    id: int
    name: str
    hostname: str
    ip_address: str
    device_type: DeviceType
    vendor: str
    model: Optional[str]
    os_version: Optional[str]
    is_active: bool
    is_reachable: bool
    last_seen: Optional[str]
    snmp_version: int
    ssh_port: int
    netconf_port: int
    netbox_id: Optional[int]
    location: Optional[str]
    description: Optional[str]
    tags: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
