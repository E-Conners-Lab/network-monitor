"""pyATS/Genie driver for structured CLI parsing (BGP/OSPF monitoring)."""

import logging
from typing import Any, Optional

from src.drivers.base import (
    CommandDriver,
    ConnectionParams,
    DevicePlatform,
    DriverResult,
    DriverType,
)

logger = logging.getLogger(__name__)

# Platform mapping from our DevicePlatform to pyATS os/platform
PLATFORM_MAP = {
    DevicePlatform.CISCO_IOS: {"os": "ios", "platform": "ios"},
    DevicePlatform.CISCO_IOS_XE: {"os": "iosxe", "platform": "csr1000v"},
    DevicePlatform.CISCO_NX_OS: {"os": "nxos", "platform": "n9k"},
    DevicePlatform.CISCO_ASA: {"os": "asa", "platform": "asa"},
}


class PyATSDriver(CommandDriver):
    """Driver using pyATS/Genie for structured CLI parsing.

    This driver is best suited for:
    - BGP neighbor state monitoring
    - OSPF neighbor state monitoring
    - Routing table analysis
    - Any CLI output that Genie has parsers for

    It uses unicon for connection management and genie for parsing.
    """

    driver_type = DriverType.SSH

    def __init__(self, params: ConnectionParams):
        super().__init__(params)
        self._device = None
        self._testbed = None

    def connect(self) -> DriverResult:
        """Establish connection to the device using pyATS/unicon."""
        try:
            from pyats.topology import loader
            from genie.testbed import load as genie_load

            platform_info = PLATFORM_MAP.get(
                self.params.platform, {"os": "ios", "platform": "ios"}
            )

            # Build testbed dict dynamically (pyATS 24.x format)
            testbed_dict = {
                "devices": {
                    "device": {
                        "os": platform_info["os"],
                        "type": platform_info["platform"],
                        "credentials": {
                            "default": {
                                "username": self.params.username or "",
                                "password": self.params.password or "",
                            }
                        },
                        "connections": {
                            "cli": {
                                "protocol": "ssh",
                                "ip": self.params.host,
                                "port": self.params.port or 22,
                            }
                        },
                    }
                }
            }

            # Add enable password if provided
            if self.params.enable_password:
                testbed_dict["devices"]["device"]["credentials"]["enable"] = {
                    "password": self.params.enable_password
                }

            self._testbed = genie_load(testbed_dict)
            self._device = self._testbed.devices["device"]

            # Connect with timeout and error handling
            self._device.connect(
                learn_hostname=True,
                init_config_commands=[],
                log_stdout=False,
            )

            self._connected = True
            logger.info(f"Connected to {self.params.host} via pyATS")
            return DriverResult(success=True, data={"hostname": self._device.hostname})

        except ImportError as e:
            error_msg = f"pyATS/Genie not installed: {e}"
            logger.error(error_msg)
            return DriverResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Failed to connect via pyATS: {e}"
            logger.error(error_msg)
            return DriverResult(success=False, error=error_msg)

    def disconnect(self) -> None:
        """Close the pyATS connection."""
        if self._device and self._connected:
            try:
                self._device.disconnect()
                logger.info(f"Disconnected from {self.params.host}")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._connected = False
                self._device = None

    def is_alive(self) -> bool:
        """Check if the connection is still alive."""
        if not self._device or not self._connected:
            return False
        try:
            return self._device.is_connected()
        except Exception:
            return False

    def execute_command(self, command: str) -> DriverResult:
        """Execute a command and return raw output."""
        if not self._connected or not self._device:
            return DriverResult(success=False, error="Not connected")

        try:
            output = self._device.execute(command)
            return DriverResult(success=True, data=output, raw_output=output)
        except Exception as e:
            return DriverResult(success=False, error=str(e))

    def execute_commands(self, commands: list[str]) -> DriverResult:
        """Execute multiple commands."""
        if not self._connected or not self._device:
            return DriverResult(success=False, error="Not connected")

        results = []
        for cmd in commands:
            result = self.execute_command(cmd)
            results.append({"command": cmd, "output": result.data, "success": result.success})

        return DriverResult(success=True, data=results)

    def configure(self, commands: list[str]) -> DriverResult:
        """Configure the device."""
        if not self._connected or not self._device:
            return DriverResult(success=False, error="Not connected")

        try:
            output = self._device.configure(commands)
            return DriverResult(success=True, data=output, raw_output=str(output))
        except Exception as e:
            return DriverResult(success=False, error=str(e))

    def parse(self, command: str) -> DriverResult:
        """Execute a command and parse it using Genie parsers.

        Returns structured data from CLI output.
        """
        if not self._connected or not self._device:
            return DriverResult(success=False, error="Not connected")

        try:
            parsed = self._device.parse(command)
            return DriverResult(success=True, data=parsed)
        except Exception as e:
            error_msg = str(e)
            # Check if it's a "no parser" error
            if "Could not find parser" in error_msg:
                logger.warning(f"No Genie parser for command: {command}")
                # Fall back to raw output
                raw_result = self.execute_command(command)
                return DriverResult(
                    success=False,
                    error=f"No parser available for: {command}",
                    raw_output=raw_result.data,
                )
            return DriverResult(success=False, error=error_msg)

    def learn(self, feature: str) -> DriverResult:
        """Learn a feature using Genie.

        Features include: bgp, ospf, interface, routing, vrf, etc.
        Returns comprehensive structured data.
        """
        if not self._connected or not self._device:
            return DriverResult(success=False, error="Not connected")

        try:
            from genie.libs.ops.bgp.bgp import Bgp
            from genie.libs.ops.ospf.ospf import Ospf
            from genie.libs.ops.routing.routing import Routing
            from genie.libs.ops.interface.interface import Interface

            feature_map = {
                "bgp": Bgp,
                "ospf": Ospf,
                "routing": Routing,
                "interface": Interface,
            }

            if feature.lower() not in feature_map:
                # Use generic learn
                learned = self._device.learn(feature)
            else:
                feature_cls = feature_map[feature.lower()]
                learned = feature_cls(device=self._device)
                learned.learn()

            return DriverResult(success=True, data=learned.info if hasattr(learned, "info") else learned)
        except Exception as e:
            return DriverResult(success=False, error=str(e))

    # Convenience methods for common monitoring tasks

    def get_bgp_neighbors(self) -> DriverResult:
        """Get BGP neighbor states.

        Returns structured data about all BGP neighbors.
        """
        # Try parsing "show ip bgp summary" first (faster)
        result = self.parse("show ip bgp summary")
        if result.success:
            return result

        # Fall back to "show bgp all summary" for VRF support
        result = self.parse("show bgp all summary")
        if result.success:
            return result

        # Try learning full BGP state
        return self.learn("bgp")

    def get_ospf_neighbors(self) -> DriverResult:
        """Get OSPF neighbor states.

        Returns structured data about all OSPF neighbors.
        """
        result = self.parse("show ip ospf neighbor")
        if result.success:
            return result

        # Try learning full OSPF state
        return self.learn("ospf")

    def get_routing_table(self, vrf: Optional[str] = None) -> DriverResult:
        """Get the routing table.

        Args:
            vrf: Optional VRF name. If None, gets global table.
        """
        if vrf:
            command = f"show ip route vrf {vrf}"
        else:
            command = "show ip route"

        return self.parse(command)

    def get_interface_status(self) -> DriverResult:
        """Get interface status information."""
        result = self.parse("show ip interface brief")
        if result.success:
            return result

        return self.learn("interface")


def extract_bgp_neighbor_states(bgp_data: dict) -> list[dict]:
    """Extract BGP neighbor states from Genie parsed data.

    Args:
        bgp_data: Data returned from get_bgp_neighbors() or learn("bgp")

    Returns:
        List of dicts with neighbor info: {neighbor, state, as, prefixes_received, etc.}
    """
    neighbors = []

    # Handle "show ip bgp summary" parsed output
    if "vrf" in bgp_data:
        for vrf_name, vrf_data in bgp_data.get("vrf", {}).items():
            for neighbor_ip, neighbor_info in vrf_data.get("neighbor", {}).items():

                # Get address family data - key can be empty string '', 'ipv4 unicast', etc.
                af_data = neighbor_info.get("address_family", {})
                # Try multiple possible keys
                ipv4_data = af_data.get("") or af_data.get("ipv4 unicast") or af_data.get("ipv4_unicast") or {}
                # If still empty, try first available address family
                if not ipv4_data and af_data:
                    ipv4_data = next(iter(af_data.values()), {})

                # state_pfxrcd is always a string - can be numeric string like "0", "2" or state like "Idle"
                state_pfxrcd = ipv4_data.get("state_pfxrcd", "")

                # Determine actual state
                # If state_pfxrcd is a numeric string, neighbor is established
                # If it's a non-numeric string (like "Idle", "Active"), that's the state
                if state_pfxrcd.isdigit():
                    # Numeric string means neighbor is established and receiving prefixes
                    state = "established"
                    prefixes = int(state_pfxrcd)
                elif state_pfxrcd:
                    # It's a state string like "Idle" or "Active"
                    state = state_pfxrcd.lower()
                    prefixes = 0
                else:
                    # Check if we have session_state at neighbor level
                    state = neighbor_info.get("session_state", "unknown")
                    if state and isinstance(state, str):
                        state = state.lower()
                    else:
                        state = "unknown"
                    prefixes = 0

                neighbors.append({
                    "vrf": vrf_name,
                    "neighbor": neighbor_ip,
                    "remote_as": ipv4_data.get("as", neighbor_info.get("remote_as", "N/A")),
                    "state": state,
                    "uptime": ipv4_data.get("up_down", neighbor_info.get("up_down", "N/A")),
                    "prefixes_received": prefixes,
                })
    # Handle learned BGP data
    elif "instance" in bgp_data:
        for instance_name, instance_data in bgp_data.get("instance", {}).items():
            for vrf_name, vrf_data in instance_data.get("vrf", {}).items():
                for neighbor_ip, neighbor_info in vrf_data.get("neighbor", {}).items():
                    state = neighbor_info.get("session_state", "unknown")
                    neighbors.append({
                        "vrf": vrf_name,
                        "neighbor": neighbor_ip,
                        "remote_as": neighbor_info.get("remote_as", "N/A"),
                        "state": state if isinstance(state, str) else str(state),
                        "uptime": neighbor_info.get("up_time", "N/A"),
                        "prefixes_received": neighbor_info.get("address_family", {})
                        .get("ipv4 unicast", {})
                        .get("prefixes", {})
                        .get("received", 0),
                    })

    return neighbors


def extract_ospf_neighbor_states(ospf_data: dict) -> list[dict]:
    """Extract OSPF neighbor states from Genie parsed data.

    Args:
        ospf_data: Data returned from get_ospf_neighbors() or learn("ospf")

    Returns:
        List of dicts with neighbor info: {neighbor, state, interface, etc.}
    """
    neighbors = []

    # Handle "show ip ospf neighbor" parsed output
    if "interfaces" in ospf_data:
        for intf_name, intf_data in ospf_data.get("interfaces", {}).items():
            for neighbor_id, neighbor_info in intf_data.get("neighbors", {}).items():
                neighbors.append({
                    "interface": intf_name,
                    "neighbor_id": neighbor_id,
                    "address": neighbor_info.get("address", "N/A"),
                    "state": neighbor_info.get("state", "unknown"),
                    "dead_time": neighbor_info.get("dead_time", "N/A"),
                    "priority": neighbor_info.get("priority", 0),
                })
    # Handle learned OSPF data
    elif "vrf" in ospf_data:
        for vrf_name, vrf_data in ospf_data.get("vrf", {}).items():
            for area_id, area_data in vrf_data.get("address_family", {}).get("ipv4", {}).get("instance", {}).items():
                for intf_name, intf_data in area_data.get("interfaces", {}).items():
                    for neighbor_id, neighbor_info in intf_data.get("neighbors", {}).items():
                        neighbors.append({
                            "vrf": vrf_name,
                            "area": area_id,
                            "interface": intf_name,
                            "neighbor_id": neighbor_id,
                            "state": neighbor_info.get("state", "unknown"),
                            "dead_time": neighbor_info.get("dead_timer", "N/A"),
                        })

    return neighbors
