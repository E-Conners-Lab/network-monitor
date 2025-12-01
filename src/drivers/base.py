"""Base driver interface for network device communication."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class DriverType(Enum):
    """Supported driver types."""

    SSH = "ssh"
    SNMP = "snmp"
    NETCONF = "netconf"
    REST = "rest"


class DevicePlatform(Enum):
    """Supported device platforms for driver selection."""

    CISCO_IOS = "cisco_ios"
    CISCO_IOS_XE = "cisco_ios_xe"
    CISCO_NX_OS = "cisco_nxos"
    CISCO_ASA = "cisco_asa"


@dataclass
class ConnectionParams:
    """Parameters for connecting to a device."""

    host: str
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = None
    timeout: int = 30

    # SSH specific
    enable_password: Optional[str] = None
    ssh_key: Optional[str] = None

    # SNMP specific
    snmp_community: Optional[str] = None
    snmp_version: int = 2

    # Platform for driver selection
    platform: DevicePlatform = DevicePlatform.CISCO_IOS


@dataclass
class DriverResult:
    """Result from a driver operation."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    raw_output: Optional[str] = None


class BaseDriver(ABC):
    """Abstract base class for all device drivers."""

    driver_type: DriverType

    def __init__(self, params: ConnectionParams):
        self.params = params
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self) -> DriverResult:
        """Establish connection to the device."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the device."""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if the connection is still alive."""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class CommandDriver(BaseDriver):
    """Base class for drivers that execute commands (SSH, NETCONF)."""

    @abstractmethod
    def execute_command(self, command: str) -> DriverResult:
        """Execute a single command on the device."""
        pass

    @abstractmethod
    def execute_commands(self, commands: list[str]) -> DriverResult:
        """Execute multiple commands on the device."""
        pass

    @abstractmethod
    def configure(self, commands: list[str]) -> DriverResult:
        """Enter configuration mode and execute commands."""
        pass


class PollingDriver(BaseDriver):
    """Base class for drivers that poll data (SNMP)."""

    @abstractmethod
    def get(self, oid: str) -> DriverResult:
        """Get a single OID value."""
        pass

    @abstractmethod
    def get_bulk(self, oids: list[str]) -> DriverResult:
        """Get multiple OID values."""
        pass

    @abstractmethod
    def walk(self, oid: str) -> DriverResult:
        """Walk an OID tree."""
        pass
