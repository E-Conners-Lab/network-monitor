"""Device schemas."""

from datetime import datetime

from pydantic import BaseModel

from src.models.device import DeviceType


class DeviceCreate(BaseModel):
    """Schema for creating a new device."""

    name: str
    hostname: str
    ip_address: str
    device_type: DeviceType
    vendor: str = "cisco"
    model: str | None = None
    os_version: str | None = None
    snmp_community: str | None = None
    snmp_version: int = 2
    ssh_port: int = 22
    netconf_port: int = 830
    netbox_id: int | None = None
    location: str | None = None
    description: str | None = None
    tags: dict | None = None


class DeviceUpdate(BaseModel):
    """Schema for updating a device."""

    name: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    device_type: DeviceType | None = None
    vendor: str | None = None
    model: str | None = None
    os_version: str | None = None
    is_active: bool | None = None
    snmp_community: str | None = None
    snmp_version: int | None = None
    ssh_port: int | None = None
    netconf_port: int | None = None
    location: str | None = None
    description: str | None = None
    tags: dict | None = None


class DeviceResponse(BaseModel):
    """Schema for device response."""

    id: int
    name: str
    hostname: str
    ip_address: str
    device_type: DeviceType
    vendor: str
    model: str | None
    os_version: str | None
    is_active: bool
    is_reachable: bool
    last_seen: str | None
    snmp_version: int
    ssh_port: int
    netconf_port: int
    netbox_id: int | None
    location: str | None
    description: str | None
    tags: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
