"""Health check service for device connectivity testing."""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.drivers import (
    ConnectionParams,
    DevicePlatform,
    SSHDriver,
    SNMPDriver,
)

logger = logging.getLogger(__name__)


@dataclass
class PingResult:
    """Result of a ping check."""

    success: bool
    latency_ms: Optional[float] = None
    packet_loss: float = 100.0
    error: Optional[str] = None


@dataclass
class ConnectivityResult:
    """Result of all connectivity checks for a device."""

    device_id: int
    device_name: str
    ip_address: str
    timestamp: datetime
    ping: Optional[PingResult] = None
    snmp: Optional[dict] = None
    ssh: Optional[dict] = None
    netconf: Optional[dict] = None
    overall_reachable: bool = False


async def ping_host(host: str, count: int = 3, timeout: int = 5) -> PingResult:
    """
    Ping a host and return the result.

    Args:
        host: IP address or hostname to ping
        count: Number of ping packets to send
        timeout: Timeout in seconds

    Returns:
        PingResult with success status, latency, and packet loss
    """
    try:
        # Use system ping command (works on both Linux and macOS)
        # -c: count, -W: timeout (Linux) or -t: timeout (macOS)
        import platform

        if platform.system().lower() == "darwin":  # macOS
            cmd = ["ping", "-c", str(count), "-t", str(timeout), host]
        else:  # Linux
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout + 5
        )

        output = stdout.decode()

        if process.returncode == 0:
            # Parse output for latency and packet loss
            latency = None
            packet_loss = 0.0

            for line in output.split("\n"):
                # Parse average latency (format varies by OS)
                if "avg" in line.lower() or "average" in line.lower():
                    # macOS: round-trip min/avg/max/stddev = 1.234/2.345/3.456/0.567 ms
                    # Linux: rtt min/avg/max/mdev = 1.234/2.345/3.456/0.567 ms
                    parts = line.split("=")
                    if len(parts) >= 2:
                        stats = parts[1].strip().split("/")
                        if len(stats) >= 2:
                            try:
                                latency = float(stats[1])
                            except ValueError:
                                pass

                # Parse packet loss
                if "packet loss" in line.lower() or "loss" in line.lower():
                    for part in line.split():
                        if "%" in part:
                            try:
                                packet_loss = float(part.replace("%", ""))
                            except ValueError:
                                pass
                            break

            return PingResult(
                success=True,
                latency_ms=latency,
                packet_loss=packet_loss,
            )
        else:
            return PingResult(
                success=False,
                error=f"Ping failed with return code {process.returncode}",
            )

    except asyncio.TimeoutError:
        return PingResult(success=False, error="Ping timed out")
    except Exception as e:
        logger.error(f"Ping error for {host}: {e}")
        return PingResult(success=False, error=str(e))


def check_snmp(
    host: str,
    community: str = "public",
    port: int = 161,
    timeout: int = 5,
) -> dict:
    """
    Check SNMP connectivity to a device.

    Returns:
        dict with success status and system info or error
    """
    try:
        params = ConnectionParams(
            host=host,
            snmp_community=community,
            port=port,
            timeout=timeout,
        )

        driver = SNMPDriver(params)
        result = driver.connect()

        if result.success:
            # Get system info
            sys_info = driver.get_system_info()
            driver.disconnect()

            if sys_info.success:
                return {
                    "success": True,
                    "system_name": sys_info.data.get("name"),
                    "system_description": sys_info.data.get("description"),
                    "uptime": sys_info.data.get("uptime"),
                }
            return {"success": True, "system_name": None}
        else:
            return {"success": False, "error": result.error}

    except Exception as e:
        logger.error(f"SNMP check error for {host}: {e}")
        return {"success": False, "error": str(e)}


def check_ssh(
    host: str,
    username: str,
    password: str,
    platform: DevicePlatform = DevicePlatform.CISCO_IOS,
    port: int = 22,
    timeout: int = 30,
    enable_password: Optional[str] = None,
) -> dict:
    """
    Check SSH connectivity to a device.

    Returns:
        dict with success status and version info or error
    """
    try:
        params = ConnectionParams(
            host=host,
            username=username,
            password=password,
            port=port,
            timeout=timeout,
            platform=platform,
            enable_password=enable_password,
        )

        driver = SSHDriver(params)
        result = driver.connect()

        if result.success:
            # Get version info
            version_result = driver.get_version()
            driver.disconnect()

            if version_result.success:
                return {
                    "success": True,
                    "version_output": version_result.data[:500] if version_result.data else None,
                }
            return {"success": True, "version_output": None}
        else:
            return {"success": False, "error": result.error}

    except Exception as e:
        logger.error(f"SSH check error for {host}: {e}")
        return {"success": False, "error": str(e)}


async def check_device_connectivity(
    device_id: int,
    device_name: str,
    ip_address: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    enable_password: Optional[str] = None,
    snmp_community: str = "public",
    platform: DevicePlatform = DevicePlatform.CISCO_IOS,
    check_ping: bool = True,
    check_snmp: bool = True,
    check_ssh: bool = True,
) -> ConnectivityResult:
    """
    Run all connectivity checks for a device.

    Args:
        device_id: Database ID of the device
        device_name: Name of the device
        ip_address: IP address to check
        username: SSH username
        password: SSH password
        enable_password: Enable password for SSH
        snmp_community: SNMP community string
        platform: Device platform for driver selection
        check_ping: Whether to run ping check
        check_snmp: Whether to run SNMP check
        check_ssh: Whether to run SSH check

    Returns:
        ConnectivityResult with results of all checks
    """
    result = ConnectivityResult(
        device_id=device_id,
        device_name=device_name,
        ip_address=ip_address,
        timestamp=datetime.utcnow(),
    )

    # Run ping check (async)
    if check_ping:
        result.ping = await ping_host(ip_address)

    # Run SNMP check (sync, but quick)
    if check_snmp:
        result.snmp = globals()["check_snmp"](ip_address, snmp_community)

    # Run SSH check (sync, can be slow)
    if check_ssh and username and password:
        result.ssh = globals()["check_ssh"](
            ip_address,
            username,
            password,
            platform,
            enable_password=enable_password,
        )

    # Determine overall reachability
    result.overall_reachable = (
        (result.ping and result.ping.success)
        or (result.snmp and result.snmp.get("success"))
        or (result.ssh and result.ssh.get("success"))
    )

    return result


class HealthCheckService:
    """Service for managing device health checks."""

    def __init__(self):
        self._running_checks: dict[int, asyncio.Task] = {}

    async def check_device(
        self,
        device_id: int,
        device_name: str,
        ip_address: str,
        **kwargs,
    ) -> ConnectivityResult:
        """Run connectivity checks for a single device."""
        return await check_device_connectivity(
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            **kwargs,
        )

    async def check_devices(
        self,
        devices: list[dict],
        max_concurrent: int = 10,
    ) -> list[ConnectivityResult]:
        """
        Run connectivity checks for multiple devices concurrently.

        Args:
            devices: List of device dicts with id, name, ip_address, etc.
            max_concurrent: Maximum concurrent checks

        Returns:
            List of ConnectivityResult for each device
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_with_semaphore(device: dict) -> ConnectivityResult:
            async with semaphore:
                return await self.check_device(**device)

        tasks = [check_with_semaphore(device) for device in devices]
        return await asyncio.gather(*tasks)
