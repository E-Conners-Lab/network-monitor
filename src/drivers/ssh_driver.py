"""SSH driver using Netmiko for Cisco device communication."""

import logging

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
from netmiko.exceptions import NetmikoBaseException

from src.drivers.base import (
    CommandDriver,
    ConnectionParams,
    DevicePlatform,
    DriverResult,
    DriverType,
)

logger = logging.getLogger(__name__)


# Map our platform enum to Netmiko device types
PLATFORM_TO_NETMIKO = {
    DevicePlatform.CISCO_IOS: "cisco_ios",
    DevicePlatform.CISCO_IOS_XE: "cisco_xe",
    DevicePlatform.CISCO_NX_OS: "cisco_nxos",
    DevicePlatform.CISCO_ASA: "cisco_asa",
}


class SSHDriver(CommandDriver):
    """SSH driver for Cisco devices using Netmiko."""

    driver_type = DriverType.SSH

    def __init__(self, params: ConnectionParams):
        super().__init__(params)
        self._connection: ConnectHandler | None = None

    def connect(self) -> DriverResult:
        """Establish SSH connection to the device."""
        try:
            device_type = PLATFORM_TO_NETMIKO.get(self.params.platform, "cisco_ios")

            connection_params = {
                "device_type": device_type,
                "host": self.params.host,
                "username": self.params.username,
                "password": self.params.password,
                "port": self.params.port or 22,
                "timeout": self.params.timeout,
                "conn_timeout": self.params.timeout,
            }

            # Add enable password if provided
            if self.params.enable_password:
                connection_params["secret"] = self.params.enable_password

            # Add SSH key if provided
            if self.params.ssh_key:
                connection_params["use_keys"] = True
                connection_params["key_file"] = self.params.ssh_key

            logger.info(f"Connecting to {self.params.host} via SSH...")
            self._connection = ConnectHandler(**connection_params)
            self._connected = True

            # Enter enable mode if we have an enable password
            if self.params.enable_password:
                self._connection.enable()

            logger.info(f"Successfully connected to {self.params.host}")
            return DriverResult(success=True, data={"connected": True})

        except NetmikoAuthenticationException as e:
            logger.error(f"Authentication failed for {self.params.host}: {e}")
            return DriverResult(success=False, error=f"Authentication failed: {e}")
        except NetmikoTimeoutException as e:
            logger.error(f"Connection timeout for {self.params.host}: {e}")
            return DriverResult(success=False, error=f"Connection timeout: {e}")
        except NetmikoBaseException as e:
            logger.error(f"Netmiko error for {self.params.host}: {e}")
            return DriverResult(success=False, error=f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.params.host}: {e}")
            return DriverResult(success=False, error=f"Unexpected error: {e}")

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self._connection:
            try:
                self._connection.disconnect()
                logger.info(f"Disconnected from {self.params.host}")
            except Exception as e:
                logger.warning(f"Error disconnecting from {self.params.host}: {e}")
            finally:
                self._connection = None
                self._connected = False

    def is_alive(self) -> bool:
        """Check if SSH connection is still alive."""
        if not self._connection:
            return False
        try:
            return self._connection.is_alive()
        except Exception:
            return False

    def execute_command(self, command: str) -> DriverResult:
        """Execute a single command on the device."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            logger.debug(f"Executing command on {self.params.host}: {command}")
            output = self._connection.send_command(command)
            return DriverResult(success=True, data=output, raw_output=output)
        except Exception as e:
            logger.error(f"Error executing command on {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def execute_commands(self, commands: list[str]) -> DriverResult:
        """Execute multiple commands on the device."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            results = {}
            for command in commands:
                logger.debug(f"Executing command on {self.params.host}: {command}")
                output = self._connection.send_command(command)
                results[command] = output
            return DriverResult(success=True, data=results)
        except Exception as e:
            logger.error(f"Error executing commands on {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def configure(self, commands: list[str]) -> DriverResult:
        """Enter configuration mode and execute commands."""
        if not self._connected or not self._connection:
            return DriverResult(success=False, error="Not connected")

        try:
            logger.info(f"Sending config commands to {self.params.host}")
            output = self._connection.send_config_set(commands)
            return DriverResult(success=True, data=output, raw_output=output)
        except Exception as e:
            logger.error(f"Error configuring {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    # Convenience methods for common operations

    def get_version(self) -> DriverResult:
        """Get device version information."""
        return self.execute_command("show version")

    def get_interfaces(self) -> DriverResult:
        """Get interface status."""
        return self.execute_command("show ip interface brief")

    def get_running_config(self) -> DriverResult:
        """Get running configuration."""
        return self.execute_command("show running-config")

    def get_cpu_utilization(self) -> DriverResult:
        """Get CPU utilization."""
        if self.params.platform == DevicePlatform.CISCO_ASA:
            return self.execute_command("show cpu usage")
        return self.execute_command("show processes cpu sorted | include CPU")

    def get_memory_utilization(self) -> DriverResult:
        """Get memory utilization."""
        if self.params.platform == DevicePlatform.CISCO_ASA:
            return self.execute_command("show memory")
        return self.execute_command("show memory statistics")

    def get_bgp_neighbors(self) -> DriverResult:
        """Get BGP neighbor status."""
        return self.execute_command("show ip bgp summary")

    def get_ospf_neighbors(self) -> DriverResult:
        """Get OSPF neighbor status."""
        return self.execute_command("show ip ospf neighbor")

    def enable_interface(self, interface: str) -> DriverResult:
        """Enable (no shutdown) an interface."""
        commands = [
            f"interface {interface}",
            "no shutdown",
        ]
        return self.configure(commands)

    def disable_interface(self, interface: str) -> DriverResult:
        """Disable (shutdown) an interface."""
        commands = [
            f"interface {interface}",
            "shutdown",
        ]
        return self.configure(commands)

    def clear_bgp_neighbor(self, neighbor_ip: str, soft: bool = True) -> DriverResult:
        """Clear a BGP neighbor session."""
        if soft:
            command = f"clear ip bgp {neighbor_ip} soft"
        else:
            command = f"clear ip bgp {neighbor_ip}"
        return self.execute_command(command)

    def save_config(self) -> DriverResult:
        """Save running config to startup config."""
        return self._connection.save_config() if self._connection else DriverResult(
            success=False, error="Not connected"
        )
