"""NETCONF driver for IOS-XE devices."""

import logging
from xml.etree import ElementTree as ET

from ncclient import manager
from ncclient.operations import RPCError
from ncclient.transport.errors import AuthenticationError, SSHError

from src.drivers.base import (
    CommandDriver,
    ConnectionParams,
    DriverResult,
    DriverType,
)

logger = logging.getLogger(__name__)


# Common NETCONF filters for Cisco IOS-XE
class NetconfFilters:
    """NETCONF filter templates for common operations."""

    # Get running config
    RUNNING_CONFIG = """
        <filter>
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"/>
        </filter>
    """

    # Get interfaces
    INTERFACES = """
        <filter>
            <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"/>
        </filter>
    """

    # Get interface statistics
    INTERFACE_STATS = """
        <filter>
            <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"/>
        </filter>
    """

    # Get CPU utilization
    CPU_USAGE = """
        <filter>
            <cpu-usage xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-process-cpu-oper"/>
        </filter>
    """

    # Get memory statistics
    MEMORY_STATS = """
        <filter>
            <memory-statistics xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-memory-oper"/>
        </filter>
    """

    # Get BGP neighbors
    BGP_NEIGHBORS = """
        <filter>
            <bgp-state-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp-oper"/>
        </filter>
    """

    # Get OSPF neighbors
    OSPF_NEIGHBORS = """
        <filter>
            <ospf-oper-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-ospf-oper"/>
        </filter>
    """


class NetconfDriver(CommandDriver):
    """NETCONF driver for Cisco IOS-XE devices."""

    driver_type = DriverType.NETCONF

    def __init__(self, params: ConnectionParams):
        super().__init__(params)
        self._connection: manager.Manager | None = None

    def connect(self) -> DriverResult:
        """Establish NETCONF connection to the device."""
        try:
            port = self.params.port or 830

            logger.info(f"Connecting to {self.params.host} via NETCONF...")
            self._connection = manager.connect(
                host=self.params.host,
                port=port,
                username=self.params.username,
                password=self.params.password,
                hostkey_verify=False,
                device_params={"name": "iosxe"},
                timeout=self.params.timeout,
            )
            self._connected = True

            logger.info(f"Successfully connected to {self.params.host} via NETCONF")
            return DriverResult(
                success=True,
                data={
                    "connected": True,
                    "session_id": self._connection.session_id,
                    "capabilities": list(self._connection.server_capabilities),
                },
            )

        except AuthenticationError as e:
            logger.error(f"NETCONF authentication failed for {self.params.host}: {e}")
            return DriverResult(success=False, error=f"Authentication failed: {e}")
        except SSHError as e:
            logger.error(f"NETCONF SSH error for {self.params.host}: {e}")
            return DriverResult(success=False, error=f"SSH error: {e}")
        except Exception as e:
            logger.error(f"NETCONF connection error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def disconnect(self) -> None:
        """Close NETCONF connection."""
        if self._connection:
            try:
                self._connection.close_session()
                logger.info(f"NETCONF session closed for {self.params.host}")
            except Exception as e:
                logger.warning(f"Error closing NETCONF session for {self.params.host}: {e}")
            finally:
                self._connection = None
                self._connected = False

    def is_alive(self) -> bool:
        """Check if NETCONF session is still alive."""
        if not self._connection:
            return False
        return self._connection.connected

    def execute_command(self, command: str) -> DriverResult:
        """Execute a CLI command via NETCONF (if supported)."""
        # Not all devices support CLI via NETCONF
        # This is a placeholder for devices that do
        return DriverResult(
            success=False, error="CLI commands not supported via NETCONF. Use get_config or edit_config."
        )

    def execute_commands(self, commands: list[str]) -> DriverResult:
        """Execute multiple CLI commands via NETCONF."""
        return DriverResult(
            success=False, error="CLI commands not supported via NETCONF. Use get_config or edit_config."
        )

    def configure(self, commands: list[str]) -> DriverResult:
        """Configure device via NETCONF edit-config."""
        # For NETCONF, commands should be XML config snippets
        return DriverResult(
            success=False,
            error="Use edit_config with XML payload instead of CLI commands",
        )

    def get_config(self, source: str = "running", filter_xml: str = None) -> DriverResult:
        """Get device configuration."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            if filter_xml:
                result = self._connection.get_config(source=source, filter=filter_xml)
            else:
                result = self._connection.get_config(source=source)

            return DriverResult(success=True, data=result.data_xml, raw_output=result.xml)
        except RPCError as e:
            logger.error(f"NETCONF RPC error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"NETCONF get_config error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def get(self, filter_xml: str) -> DriverResult:
        """Get operational data."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            result = self._connection.get(filter=filter_xml)
            return DriverResult(success=True, data=result.data_xml, raw_output=result.xml)
        except RPCError as e:
            logger.error(f"NETCONF RPC error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"NETCONF get error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def edit_config(
        self, config_xml: str, target: str = "running", default_operation: str = "merge"
    ) -> DriverResult:
        """Edit device configuration."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            result = self._connection.edit_config(
                target=target, config=config_xml, default_operation=default_operation
            )
            return DriverResult(success=True, data=result.xml)
        except RPCError as e:
            logger.error(f"NETCONF edit_config error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"NETCONF edit_config error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    # Convenience methods for common operations

    def get_interfaces(self) -> DriverResult:
        """Get interface configuration."""
        return self.get(NetconfFilters.INTERFACES)

    def get_interface_stats(self) -> DriverResult:
        """Get interface operational statistics."""
        return self.get(NetconfFilters.INTERFACE_STATS)

    def get_cpu_utilization(self) -> DriverResult:
        """Get CPU utilization."""
        result = self.get(NetconfFilters.CPU_USAGE)
        if result.success and result.data:
            # Parse XML to extract CPU values
            try:
                root = ET.fromstring(result.data)
                ns = {"cpu": "http://cisco.com/ns/yang/Cisco-IOS-XE-process-cpu-oper"}
                cpu_usage = root.find(".//cpu:five-seconds", ns)
                if cpu_usage is not None:
                    return DriverResult(
                        success=True,
                        data={"cpu_5sec": int(cpu_usage.text)},
                    )
            except Exception as e:
                logger.warning(f"Error parsing CPU data: {e}")
        return result

    def get_memory_stats(self) -> DriverResult:
        """Get memory statistics."""
        return self.get(NetconfFilters.MEMORY_STATS)

    def get_bgp_neighbors(self) -> DriverResult:
        """Get BGP neighbor information."""
        return self.get(NetconfFilters.BGP_NEIGHBORS)

    def get_ospf_neighbors(self) -> DriverResult:
        """Get OSPF neighbor information."""
        return self.get(NetconfFilters.OSPF_NEIGHBORS)

    def enable_interface(self, interface_name: str) -> DriverResult:
        """Enable (no shutdown) an interface."""
        config = f"""
        <config>
            <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
                <interface>
                    <name>{interface_name}</name>
                    <enabled>true</enabled>
                </interface>
            </interfaces>
        </config>
        """
        return self.edit_config(config)

    def disable_interface(self, interface_name: str) -> DriverResult:
        """Disable (shutdown) an interface."""
        config = f"""
        <config>
            <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
                <interface>
                    <name>{interface_name}</name>
                    <enabled>false</enabled>
                </interface>
            </interfaces>
        </config>
        """
        return self.edit_config(config)

    def save_config(self) -> DriverResult:
        """Save running config to startup (copy run start)."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            # Use Cisco-specific RPC for save config
            save_rpc = """
            <save-config xmlns="http://cisco.com/yang/cisco-ia"/>
            """
            result = self._connection.dispatch(ET.fromstring(save_rpc))
            return DriverResult(success=True, data=result.xml)
        except Exception as e:
            logger.error(f"Error saving config on {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))
