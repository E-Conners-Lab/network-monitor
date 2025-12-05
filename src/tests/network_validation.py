"""
Full Network Validation Test Suite using pyATS.

This module provides comprehensive network testing including:
- Device connectivity
- BGP neighbor validation
- OSPF neighbor validation
- Interface status checks
- Route table verification
- End-to-end path validation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.drivers.base import ConnectionParams, DevicePlatform
from src.drivers.pyats_driver import (
    PyATSDriver,
    extract_bgp_neighbor_states,
    extract_ospf_neighbor_states,
)

logger = logging.getLogger(__name__)


class TestStatus(str, Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Individual test result."""
    name: str
    status: TestStatus
    message: str
    device: str | None = None
    details: dict = field(default_factory=dict)
    duration_ms: float = 0


@dataclass
class TestSuiteResult:
    """Complete test suite result."""
    suite_name: str
    started_at: datetime
    completed_at: datetime | None = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[TestResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100

    @property
    def status(self) -> str:
        if self.failed > 0 or self.errors > 0:
            return "failed"
        if self.passed == self.total_tests:
            return "passed"
        return "partial"

    def add_result(self, result: TestResult):
        self.results.append(result)
        self.total_tests += 1
        if result.status == TestStatus.PASSED:
            self.passed += 1
        elif result.status == TestStatus.FAILED:
            self.failed += 1
        elif result.status == TestStatus.SKIPPED:
            self.skipped += 1
        else:
            self.errors += 1

    def to_dict(self) -> dict:
        # Filter out SKIPPED results - they add noise without value
        active_results = [r for r in self.results if r.status != TestStatus.SKIPPED]

        return {
            "suite_name": self.suite_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "total_tests": self.total_tests - self.skipped,  # Exclude skipped from count
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "success_rate": self.success_rate,
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "device": r.device,
                    "details": r.details,
                    "duration_ms": r.duration_ms,
                }
                for r in active_results
            ],
        }


class NetworkValidator:
    """Network validation test runner."""

    def __init__(self, devices: list[dict], credentials: dict):
        """
        Initialize the validator.

        Args:
            devices: List of device dicts with ip_address, name, vendor, etc.
            credentials: Dict with username, password, enable_password
        """
        self.devices = devices
        self.credentials = credentials
        self.drivers: dict[str, PyATSDriver] = {}

    def _get_platform(self, vendor: str) -> DevicePlatform:
        """Map vendor to platform."""
        vendor_lower = (vendor or "").lower()
        if "cisco" in vendor_lower:
            return DevicePlatform.CISCO_IOS_XE
        return DevicePlatform.CISCO_IOS

    def _connect_device(self, device: dict) -> PyATSDriver | None:
        """Connect to a device and return driver."""
        device_name = device.get("name", device.get("ip_address"))

        if device_name in self.drivers:
            driver = self.drivers[device_name]
            if driver.is_alive():
                return driver

        params = ConnectionParams(
            host=device["ip_address"],
            port=device.get("ssh_port", 22),
            username=self.credentials.get("username"),
            password=self.credentials.get("password"),
            enable_password=self.credentials.get("enable_password"),
            platform=self._get_platform(device.get("vendor")),
        )

        driver = PyATSDriver(params)
        result = driver.connect()

        if result.success:
            self.drivers[device_name] = driver
            return driver

        logger.error(f"Failed to connect to {device_name}: {result.error}")
        return None

    def _disconnect_all(self):
        """Disconnect from all devices."""
        for name, driver in self.drivers.items():
            try:
                driver.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting from {name}: {e}")
        self.drivers.clear()

    def run_full_validation(self) -> TestSuiteResult:
        """Run the complete network validation test suite."""
        suite = TestSuiteResult(
            suite_name="Full Network Validation",
            started_at=datetime.utcnow(),
        )

        try:
            # 1. Connectivity tests
            logger.info("Running connectivity tests...")
            self._run_connectivity_tests(suite)

            # 2. BGP validation
            logger.info("Running BGP validation...")
            self._run_bgp_tests(suite)

            # 3. OSPF validation
            logger.info("Running OSPF validation...")
            self._run_ospf_tests(suite)

            # 4. Interface status checks
            logger.info("Running interface status checks...")
            self._run_interface_tests(suite)

            # 5. Route table validation
            logger.info("Running route table validation...")
            self._run_routing_tests(suite)

            # 6. End-to-end path tests
            logger.info("Running end-to-end path tests...")
            self._run_path_tests(suite)

        except Exception as e:
            logger.error(f"Test suite error: {e}")
            suite.add_result(TestResult(
                name="Suite Execution",
                status=TestStatus.ERROR,
                message=f"Test suite failed with error: {str(e)}",
            ))
        finally:
            self._disconnect_all()
            suite.completed_at = datetime.utcnow()

        return suite

    def run_quick_health_check(self) -> TestSuiteResult:
        """Run a quick health check (connectivity + protocols only)."""
        suite = TestSuiteResult(
            suite_name="Quick Health Check",
            started_at=datetime.utcnow(),
        )

        try:
            self._run_connectivity_tests(suite)
            self._run_bgp_tests(suite)
            self._run_ospf_tests(suite)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            suite.add_result(TestResult(
                name="Health Check",
                status=TestStatus.ERROR,
                message=str(e),
            ))
        finally:
            self._disconnect_all()
            suite.completed_at = datetime.utcnow()

        return suite

    def _run_connectivity_tests(self, suite: TestSuiteResult):
        """Test SSH connectivity to all devices."""
        import time

        for device in self.devices:
            device_name = device.get("name", device.get("ip_address"))
            start = time.time()

            try:
                driver = self._connect_device(device)
                duration = (time.time() - start) * 1000

                if driver:
                    suite.add_result(TestResult(
                        name=f"Connectivity: {device_name}",
                        status=TestStatus.PASSED,
                        message=f"Successfully connected to {device['ip_address']}",
                        device=device_name,
                        duration_ms=duration,
                    ))
                else:
                    suite.add_result(TestResult(
                        name=f"Connectivity: {device_name}",
                        status=TestStatus.FAILED,
                        message=f"Failed to connect to {device['ip_address']}",
                        device=device_name,
                        duration_ms=duration,
                    ))
            except Exception as e:
                suite.add_result(TestResult(
                    name=f"Connectivity: {device_name}",
                    status=TestStatus.ERROR,
                    message=str(e),
                    device=device_name,
                ))

    def _run_bgp_tests(self, suite: TestSuiteResult):
        """Validate BGP neighbors on all devices."""
        import time

        for device in self.devices:
            device_name = device.get("name", device.get("ip_address"))
            driver = self.drivers.get(device_name)

            if not driver:
                suite.add_result(TestResult(
                    name=f"BGP Validation: {device_name}",
                    status=TestStatus.SKIPPED,
                    message="Device not connected",
                    device=device_name,
                ))
                continue

            start = time.time()
            try:
                bgp_result = driver.get_bgp_neighbors()
                duration = (time.time() - start) * 1000

                if not bgp_result.success:
                    # No BGP configured - this is OK for some devices
                    if "No such file" in str(bgp_result.error) or "Invalid" in str(bgp_result.error):
                        suite.add_result(TestResult(
                            name=f"BGP Validation: {device_name}",
                            status=TestStatus.SKIPPED,
                            message="BGP not configured on this device",
                            device=device_name,
                            duration_ms=duration,
                        ))
                    else:
                        suite.add_result(TestResult(
                            name=f"BGP Validation: {device_name}",
                            status=TestStatus.ERROR,
                            message=f"Error getting BGP data: {bgp_result.error}",
                            device=device_name,
                            duration_ms=duration,
                        ))
                    continue

                neighbors = extract_bgp_neighbor_states(bgp_result.data)

                if not neighbors:
                    suite.add_result(TestResult(
                        name=f"BGP Validation: {device_name}",
                        status=TestStatus.SKIPPED,
                        message="No BGP neighbors configured",
                        device=device_name,
                        duration_ms=duration,
                    ))
                    continue

                # Check each neighbor
                established = 0
                down = []

                for neighbor in neighbors:
                    neighbor_ip = neighbor.get("neighbor", "unknown")
                    state = neighbor.get("state", "unknown").lower()

                    if state == "established":
                        established += 1
                    else:
                        down.append(f"{neighbor_ip} ({state})")

                total = len(neighbors)

                if established == total:
                    suite.add_result(TestResult(
                        name=f"BGP Validation: {device_name}",
                        status=TestStatus.PASSED,
                        message=f"All {total} BGP neighbors established",
                        device=device_name,
                        details={"neighbors": neighbors},
                        duration_ms=duration,
                    ))
                else:
                    suite.add_result(TestResult(
                        name=f"BGP Validation: {device_name}",
                        status=TestStatus.FAILED,
                        message=f"{len(down)}/{total} BGP neighbors down: {', '.join(down)}",
                        device=device_name,
                        details={"neighbors": neighbors, "down": down},
                        duration_ms=duration,
                    ))

            except Exception as e:
                suite.add_result(TestResult(
                    name=f"BGP Validation: {device_name}",
                    status=TestStatus.ERROR,
                    message=str(e),
                    device=device_name,
                ))

    def _run_ospf_tests(self, suite: TestSuiteResult):
        """Validate OSPF neighbors on all devices."""
        import time

        for device in self.devices:
            device_name = device.get("name", device.get("ip_address"))
            driver = self.drivers.get(device_name)

            if not driver:
                suite.add_result(TestResult(
                    name=f"OSPF Validation: {device_name}",
                    status=TestStatus.SKIPPED,
                    message="Device not connected",
                    device=device_name,
                ))
                continue

            start = time.time()
            try:
                ospf_result = driver.get_ospf_neighbors()
                duration = (time.time() - start) * 1000

                if not ospf_result.success:
                    if "No such file" in str(ospf_result.error) or "Invalid" in str(ospf_result.error):
                        suite.add_result(TestResult(
                            name=f"OSPF Validation: {device_name}",
                            status=TestStatus.SKIPPED,
                            message="OSPF not configured on this device",
                            device=device_name,
                            duration_ms=duration,
                        ))
                    else:
                        suite.add_result(TestResult(
                            name=f"OSPF Validation: {device_name}",
                            status=TestStatus.ERROR,
                            message=f"Error getting OSPF data: {ospf_result.error}",
                            device=device_name,
                            duration_ms=duration,
                        ))
                    continue

                neighbors = extract_ospf_neighbor_states(ospf_result.data)

                if not neighbors:
                    suite.add_result(TestResult(
                        name=f"OSPF Validation: {device_name}",
                        status=TestStatus.SKIPPED,
                        message="No OSPF neighbors found",
                        device=device_name,
                        duration_ms=duration,
                    ))
                    continue

                # Check each neighbor - FULL state is healthy
                full_count = 0
                not_full = []

                for neighbor in neighbors:
                    neighbor_id = neighbor.get("neighbor_id", "unknown")
                    state = neighbor.get("state", "unknown")

                    if "FULL" in state.upper():
                        full_count += 1
                    else:
                        not_full.append(f"{neighbor_id} ({state})")

                total = len(neighbors)

                if full_count == total:
                    suite.add_result(TestResult(
                        name=f"OSPF Validation: {device_name}",
                        status=TestStatus.PASSED,
                        message=f"All {total} OSPF neighbors in FULL state",
                        device=device_name,
                        details={"neighbors": neighbors},
                        duration_ms=duration,
                    ))
                else:
                    suite.add_result(TestResult(
                        name=f"OSPF Validation: {device_name}",
                        status=TestStatus.FAILED,
                        message=f"{len(not_full)}/{total} OSPF neighbors not FULL: {', '.join(not_full)}",
                        device=device_name,
                        details={"neighbors": neighbors, "not_full": not_full},
                        duration_ms=duration,
                    ))

            except Exception as e:
                suite.add_result(TestResult(
                    name=f"OSPF Validation: {device_name}",
                    status=TestStatus.ERROR,
                    message=str(e),
                    device=device_name,
                ))

    def _run_interface_tests(self, suite: TestSuiteResult):
        """Check interface status on all devices."""
        import time

        for device in self.devices:
            device_name = device.get("name", device.get("ip_address"))
            driver = self.drivers.get(device_name)

            if not driver:
                suite.add_result(TestResult(
                    name=f"Interface Status: {device_name}",
                    status=TestStatus.SKIPPED,
                    message="Device not connected",
                    device=device_name,
                ))
                continue

            start = time.time()
            try:
                intf_result = driver.get_interface_status()
                duration = (time.time() - start) * 1000

                if not intf_result.success:
                    suite.add_result(TestResult(
                        name=f"Interface Status: {device_name}",
                        status=TestStatus.ERROR,
                        message=f"Error getting interface data: {intf_result.error}",
                        device=device_name,
                        duration_ms=duration,
                    ))
                    continue

                # Parse interface data
                interfaces = intf_result.data.get("interface", {})

                up_count = 0
                down_list = []
                admin_down = []

                for intf_name, intf_data in interfaces.items():
                    # Skip loopback and virtual interfaces for down check
                    if intf_name.lower().startswith(("lo", "null", "vlan")):
                        continue

                    status = intf_data.get("status", "down").lower()

                    if status == "up":
                        up_count += 1
                    elif "admin" in status:
                        admin_down.append(intf_name)
                    else:
                        down_list.append(intf_name)

                # Only fail if interfaces are down (not admin down)
                if not down_list:
                    suite.add_result(TestResult(
                        name=f"Interface Status: {device_name}",
                        status=TestStatus.PASSED,
                        message=f"{up_count} interfaces up, {len(admin_down)} admin-down",
                        device=device_name,
                        details={
                            "up_count": up_count,
                            "admin_down": admin_down,
                        },
                        duration_ms=duration,
                    ))
                else:
                    suite.add_result(TestResult(
                        name=f"Interface Status: {device_name}",
                        status=TestStatus.FAILED,
                        message=f"{len(down_list)} interfaces down: {', '.join(down_list)}",
                        device=device_name,
                        details={
                            "up_count": up_count,
                            "down": down_list,
                            "admin_down": admin_down,
                        },
                        duration_ms=duration,
                    ))

            except Exception as e:
                suite.add_result(TestResult(
                    name=f"Interface Status: {device_name}",
                    status=TestStatus.ERROR,
                    message=str(e),
                    device=device_name,
                ))

    def _run_routing_tests(self, suite: TestSuiteResult):
        """Validate routing tables have expected routes."""
        import time

        def has_default_route(routes: dict) -> bool:
            """Check if any route represents a default route (0.0.0.0/0)."""
            for prefix in routes.keys():
                # Match various formats: "0.0.0.0/0", "0.0.0.0", "0.0.0.0/0/0", etc.
                if prefix.startswith("0.0.0.0"):
                    return True
            return False

        for device in self.devices:
            device_name = device.get("name", device.get("ip_address"))
            driver = self.drivers.get(device_name)

            if not driver:
                suite.add_result(TestResult(
                    name=f"Route Table: {device_name}",
                    status=TestStatus.SKIPPED,
                    message="Device not connected",
                    device=device_name,
                ))
                continue

            start = time.time()
            try:
                route_result = driver.get_routing_table()
                duration = (time.time() - start) * 1000

                if not route_result.success:
                    suite.add_result(TestResult(
                        name=f"Route Table: {device_name}",
                        status=TestStatus.ERROR,
                        message=f"Error getting routing table: {route_result.error}",
                        device=device_name,
                        duration_ms=duration,
                    ))
                    continue

                # Extract route prefixes from parsed data
                # Genie parser returns: {"vrf": {"default": {"routes": {...}}}}
                vrf_data = route_result.data.get("vrf", {})
                default_vrf = vrf_data.get("default", {})
                routes = default_vrf.get("routes", {})

                route_count = len(routes)

                # Check for default route using flexible matching
                has_default = has_default_route(routes)

                if has_default:
                    suite.add_result(TestResult(
                        name=f"Route Table: {device_name}",
                        status=TestStatus.PASSED,
                        message=f"{route_count} routes in table, default route present",
                        device=device_name,
                        details={"route_count": route_count},
                        duration_ms=duration,
                    ))
                else:
                    suite.add_result(TestResult(
                        name=f"Route Table: {device_name}",
                        status=TestStatus.FAILED,
                        message=f"Missing default route (0.0.0.0/0) - {route_count} routes in table",
                        device=device_name,
                        details={
                            "route_count": route_count,
                            "missing": ["0.0.0.0/0"],
                        },
                        duration_ms=duration,
                    ))

            except Exception as e:
                suite.add_result(TestResult(
                    name=f"Route Table: {device_name}",
                    status=TestStatus.ERROR,
                    message=str(e),
                    device=device_name,
                ))

    def _run_path_tests(self, suite: TestSuiteResult):
        """Run end-to-end path validation tests."""
        import time

        # Define source-destination pairs for path testing
        # Use core routers as sources to test reachability to edges
        path_tests = []

        # Build path tests from device list
        core_devices = [d for d in self.devices if "CORE" in d.get("name", "").upper()]
        edge_devices = [d for d in self.devices if any(x in d.get("name", "").upper() for x in ["PE", "GW", "AGG"])]

        # From each core, test path to each edge device's loopback (use mgmt IP for now)
        for core in core_devices[:2]:  # Limit to first 2 cores
            for edge in edge_devices[:4]:  # Limit to first 4 edges
                if core["ip_address"] != edge["ip_address"]:
                    path_tests.append({
                        "source": core,
                        "dest_ip": edge["ip_address"],
                        "dest_name": edge.get("name", edge["ip_address"]),
                    })

        for test in path_tests:
            source = test["source"]
            source_name = source.get("name", source["ip_address"])
            dest_ip = test["dest_ip"]
            dest_name = test["dest_name"]

            driver = self.drivers.get(source_name)

            if not driver:
                suite.add_result(TestResult(
                    name=f"Path: {source_name} -> {dest_name}",
                    status=TestStatus.SKIPPED,
                    message="Source device not connected",
                    device=source_name,
                ))
                continue

            start = time.time()
            try:
                # Use ping to test reachability
                ping_result = driver.execute_command(f"ping {dest_ip} repeat 3 timeout 2")
                duration = (time.time() - start) * 1000

                if ping_result.success and ping_result.data:
                    output = ping_result.data.lower()

                    # Check for success rate
                    if "success rate is 100" in output or "!!!" in output:
                        suite.add_result(TestResult(
                            name=f"Path: {source_name} -> {dest_name}",
                            status=TestStatus.PASSED,
                            message=f"Ping from {source_name} to {dest_name} ({dest_ip}) successful",
                            device=source_name,
                            duration_ms=duration,
                        ))
                    elif "success rate is 0" in output or "....." in output:
                        suite.add_result(TestResult(
                            name=f"Path: {source_name} -> {dest_name}",
                            status=TestStatus.FAILED,
                            message=f"Ping from {source_name} to {dest_name} ({dest_ip}) failed - 0% success",
                            device=source_name,
                            duration_ms=duration,
                        ))
                    else:
                        # Partial success
                        suite.add_result(TestResult(
                            name=f"Path: {source_name} -> {dest_name}",
                            status=TestStatus.PASSED,
                            message=f"Ping from {source_name} to {dest_name} ({dest_ip}) - partial success",
                            device=source_name,
                            duration_ms=duration,
                        ))
                else:
                    suite.add_result(TestResult(
                        name=f"Path: {source_name} -> {dest_name}",
                        status=TestStatus.ERROR,
                        message=f"Ping command failed: {ping_result.error}",
                        device=source_name,
                        duration_ms=duration,
                    ))

            except Exception as e:
                suite.add_result(TestResult(
                    name=f"Path: {source_name} -> {dest_name}",
                    status=TestStatus.ERROR,
                    message=str(e),
                    device=source_name,
                ))


def run_network_validation(
    devices: list[dict],
    credentials: dict,
    test_type: str = "full"
) -> dict:
    """
    Run network validation tests.

    Args:
        devices: List of device dicts from database
        credentials: SSH credentials dict
        test_type: "full" or "quick"

    Returns:
        Test suite results as dict
    """
    validator = NetworkValidator(devices, credentials)

    if test_type == "quick":
        result = validator.run_quick_health_check()
    else:
        result = validator.run_full_validation()

    return result.to_dict()
