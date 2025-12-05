"""SNMP driver for polling device metrics."""

import logging
from typing import Any

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)
from pysnmp.proto.rfc1902 import Integer, OctetString

from src.drivers.base import (
    ConnectionParams,
    DriverResult,
    DriverType,
    PollingDriver,
)

logger = logging.getLogger(__name__)


# Common Cisco SNMP OIDs
class CiscoOIDs:
    """Common Cisco SNMP OIDs."""

    # System
    SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
    SYS_NAME = "1.3.6.1.2.1.1.5.0"
    SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

    # CPU (Cisco)
    CPU_5SEC = "1.3.6.1.4.1.9.9.109.1.1.1.1.6.1"  # 5 second CPU
    CPU_1MIN = "1.3.6.1.4.1.9.9.109.1.1.1.1.7.1"  # 1 minute CPU
    CPU_5MIN = "1.3.6.1.4.1.9.9.109.1.1.1.1.8.1"  # 5 minute CPU

    # Memory (Cisco)
    MEM_USED = "1.3.6.1.4.1.9.9.48.1.1.1.5.1"
    MEM_FREE = "1.3.6.1.4.1.9.9.48.1.1.1.6.1"

    # Interfaces
    IF_TABLE = "1.3.6.1.2.1.2.2.1"
    IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
    IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"  # 1=up, 2=down, 3=testing
    IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
    IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
    IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
    IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
    IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"

    # High capacity counters (64-bit)
    IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
    IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"

    # BGP (Cisco)
    BGP_PEER_STATE = "1.3.6.1.2.1.15.3.1.2"
    BGP_PEER_TABLE = "1.3.6.1.2.1.15.3.1"

    # ASA specific
    ASA_CONN_COUNT = "1.3.6.1.4.1.9.9.147.1.2.2.2.1.5.40.6"
    ASA_FAILOVER_STATUS = "1.3.6.1.4.1.9.9.147.1.2.1.1.1.3"

    # Interface status code mappings (RFC 2863)
    IF_OPER_STATUS_MAP = {1: "up", 2: "down", 3: "testing", 4: "unknown", 5: "dormant", 6: "notPresent", 7: "lowerLayerDown"}
    IF_ADMIN_STATUS_MAP = {1: "up", 2: "down", 3: "testing"}


class SNMPDriver(PollingDriver):
    """SNMP driver for polling device metrics."""

    driver_type = DriverType.SNMP

    def __init__(self, params: ConnectionParams):
        super().__init__(params)
        self._engine: SnmpEngine | None = None
        self._community: CommunityData | None = None
        self._transport: UdpTransportTarget | None = None

    def connect(self) -> DriverResult:
        """Initialize SNMP engine and transport."""
        try:
            self._engine = SnmpEngine()

            # Set up community string (SNMPv2c)
            community = self.params.snmp_community or "public"
            self._community = CommunityData(community, mpModel=1)  # mpModel=1 for v2c

            # Set up transport
            port = self.params.port or 161
            self._transport = UdpTransportTarget(
                (self.params.host, port),
                timeout=self.params.timeout,
                retries=2,
            )

            # Test connectivity with a simple get
            result = self.get(CiscoOIDs.SYS_DESCR)
            if result.success:
                self._connected = True
                logger.info(f"SNMP connection to {self.params.host} successful")
                return DriverResult(success=True, data={"connected": True})
            else:
                return DriverResult(success=False, error=result.error)

        except Exception as e:
            logger.error(f"SNMP connection error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def disconnect(self) -> None:
        """Clean up SNMP resources."""
        self._engine = None
        self._community = None
        self._transport = None
        self._connected = False
        logger.info(f"SNMP session closed for {self.params.host}")

    def is_alive(self) -> bool:
        """Check if SNMP is responsive."""
        if not self._connected:
            return False
        result = self.get(CiscoOIDs.SYS_UPTIME)
        return result.success

    def get(self, oid: str) -> DriverResult:
        """Get a single OID value."""
        if not self._engine or not self._community or not self._transport:
            return DriverResult(success=False, error="Not connected")

        try:
            iterator = getCmd(
                self._engine,
                self._community,
                self._transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )

            error_indication, error_status, error_index, var_binds = next(iterator)

            if error_indication:
                return DriverResult(success=False, error=str(error_indication))
            elif error_status:
                error_msg = f"{error_status.prettyPrint()} at {var_binds[int(error_index) - 1][0] if error_index else '?'}"
                return DriverResult(success=False, error=error_msg)
            else:
                if var_binds:
                    oid_returned, value = var_binds[0]
                    return DriverResult(
                        success=True,
                        data=self._convert_value(value),
                        raw_output=str(value),
                    )
                return DriverResult(success=False, error="No data returned")

        except Exception as e:
            logger.error(f"SNMP get error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def get_bulk(self, oids: list[str]) -> DriverResult:
        """Get multiple OID values."""
        if not self._engine or not self._community or not self._transport:
            return DriverResult(success=False, error="Not connected")

        try:
            object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

            iterator = getCmd(
                self._engine,
                self._community,
                self._transport,
                ContextData(),
                *object_types,
            )

            error_indication, error_status, error_index, var_binds = next(iterator)

            if error_indication:
                return DriverResult(success=False, error=str(error_indication))
            elif error_status:
                error_msg = f"{error_status.prettyPrint()}"
                return DriverResult(success=False, error=error_msg)
            else:
                results = {}
                for oid_obj, value in var_binds:
                    results[str(oid_obj)] = self._convert_value(value)
                return DriverResult(success=True, data=results)

        except Exception as e:
            logger.error(f"SNMP bulk get error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def walk(self, oid: str) -> DriverResult:
        """Walk an OID tree."""
        if not self._engine or not self._community or not self._transport:
            return DriverResult(success=False, error="Not connected")

        try:
            results = {}

            for error_indication, error_status, error_index, var_binds in nextCmd(
                self._engine,
                self._community,
                self._transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            ):
                if error_indication:
                    return DriverResult(success=False, error=str(error_indication))
                elif error_status:
                    break
                else:
                    for oid_obj, value in var_binds:
                        results[str(oid_obj)] = self._convert_value(value)

            return DriverResult(success=True, data=results)

        except Exception as e:
            logger.error(f"SNMP walk error for {self.params.host}: {e}")
            return DriverResult(success=False, error=str(e))

    def _convert_value(self, value) -> Any:
        """Convert SNMP value to Python type."""
        if isinstance(value, Integer):
            return int(value)
        elif isinstance(value, OctetString):
            try:
                return str(value)
            except UnicodeDecodeError:
                return value.prettyPrint()
        else:
            return value.prettyPrint()

    # Convenience methods for common metrics

    def get_system_info(self) -> DriverResult:
        """Get system information."""
        oids = [
            CiscoOIDs.SYS_DESCR,
            CiscoOIDs.SYS_UPTIME,
            CiscoOIDs.SYS_NAME,
            CiscoOIDs.SYS_LOCATION,
        ]
        result = self.get_bulk(oids)
        if result.success:
            return DriverResult(
                success=True,
                data={
                    "description": result.data.get(CiscoOIDs.SYS_DESCR),
                    "uptime": result.data.get(CiscoOIDs.SYS_UPTIME),
                    "name": result.data.get(CiscoOIDs.SYS_NAME),
                    "location": result.data.get(CiscoOIDs.SYS_LOCATION),
                },
            )
        return result

    def get_cpu_utilization(self) -> DriverResult:
        """Get CPU utilization metrics.

        The CPU index varies by platform (CSR1000V uses .7, physical routers use .1).
        We walk the CPU table to find the first valid entry.
        """
        # Base OIDs for CPU metrics (without index)
        cpu_5sec_base = "1.3.6.1.4.1.9.9.109.1.1.1.1.6"
        cpu_1min_base = "1.3.6.1.4.1.9.9.109.1.1.1.1.7"
        cpu_5min_base = "1.3.6.1.4.1.9.9.109.1.1.1.1.8"

        # Walk the 5-min CPU OID to find valid entries
        walk_result = self.walk(cpu_5min_base)
        if walk_result.success and walk_result.data:
            # Get the first entry's index
            for oid, value in walk_result.data.items():
                # Check if value is numeric (can be string representation of number)
                if value is not None:
                    try:
                        # Try to convert to int to validate it's a number
                        int(value)
                        # Extract the index from the OID
                        idx = oid.split('.')[-1]
                        # Now get all three metrics with this index
                        oids = [
                            f"{cpu_5sec_base}.{idx}",
                            f"{cpu_1min_base}.{idx}",
                            f"{cpu_5min_base}.{idx}",
                        ]
                        result = self.get_bulk(oids)
                        if result.success:
                            return DriverResult(
                                success=True,
                                data={
                                    "cpu_5sec": result.data.get(f"{cpu_5sec_base}.{idx}", 0),
                                    "cpu_1min": result.data.get(f"{cpu_1min_base}.{idx}", 0),
                                    "cpu_5min": result.data.get(f"{cpu_5min_base}.{idx}", 0),
                                },
                            )
                        break
                    except (ValueError, TypeError):
                        continue  # Not a valid number, try next

        # Fallback to original method for backwards compatibility
        oids = [CiscoOIDs.CPU_5SEC, CiscoOIDs.CPU_1MIN, CiscoOIDs.CPU_5MIN]
        result = self.get_bulk(oids)
        if result.success:
            return DriverResult(
                success=True,
                data={
                    "cpu_5sec": result.data.get(CiscoOIDs.CPU_5SEC, 0),
                    "cpu_1min": result.data.get(CiscoOIDs.CPU_1MIN, 0),
                    "cpu_5min": result.data.get(CiscoOIDs.CPU_5MIN, 0),
                },
            )
        return result

    def get_memory_utilization(self) -> DriverResult:
        """Get memory utilization metrics."""
        oids = [CiscoOIDs.MEM_USED, CiscoOIDs.MEM_FREE]
        result = self.get_bulk(oids)
        if result.success:
            used_raw = result.data.get(CiscoOIDs.MEM_USED, 0)
            free_raw = result.data.get(CiscoOIDs.MEM_FREE, 0)

            # Handle "No Such Instance" string responses
            try:
                used = int(used_raw) if isinstance(used_raw, (int, float)) else 0
                free = int(free_raw) if isinstance(free_raw, (int, float)) else 0
            except (ValueError, TypeError):
                used = 0
                free = 0

            total = used + free if used and free else 0
            utilization = (used / total * 100) if total > 0 else 0

            return DriverResult(
                success=True,
                data={
                    "memory_used": used,
                    "memory_free": free,
                    "memory_total": total,
                    "memory_utilization": round(utilization, 2),
                },
            )
        return result

    def get_interface_names(self) -> DriverResult:
        """Get interface names (ifDescr) indexed by ifIndex."""
        result = self.walk(CiscoOIDs.IF_DESCR)
        if result.success:
            interfaces = {}
            for oid, name in result.data.items():
                if_index = oid.split(".")[-1]
                interfaces[if_index] = str(name)
            return DriverResult(success=True, data=interfaces)
        return result

    def get_interface_status(self) -> DriverResult:
        """Get interface operational status."""
        result = self.walk(CiscoOIDs.IF_OPER_STATUS)
        if result.success:
            interfaces = {}
            for oid, status in result.data.items():
                if_index = oid.split(".")[-1]
                interfaces[if_index] = CiscoOIDs.IF_OPER_STATUS_MAP.get(status, "unknown")
            return DriverResult(success=True, data=interfaces)
        return result

    def get_interface_admin_status(self) -> DriverResult:
        """Get interface administrative status (ifAdminStatus)."""
        result = self.walk(CiscoOIDs.IF_ADMIN_STATUS)
        if result.success:
            interfaces = {}
            for oid, status in result.data.items():
                if_index = oid.split(".")[-1]
                interfaces[if_index] = CiscoOIDs.IF_ADMIN_STATUS_MAP.get(status, "unknown")
            return DriverResult(success=True, data=interfaces)
        return result

    def get_interface_counters(self, if_index: int) -> DriverResult:
        """Get interface traffic counters."""
        oids = [
            f"{CiscoOIDs.IF_IN_OCTETS}.{if_index}",
            f"{CiscoOIDs.IF_OUT_OCTETS}.{if_index}",
            f"{CiscoOIDs.IF_IN_ERRORS}.{if_index}",
            f"{CiscoOIDs.IF_OUT_ERRORS}.{if_index}",
        ]
        result = self.get_bulk(oids)
        if result.success:
            return DriverResult(
                success=True,
                data={
                    "in_octets": list(result.data.values())[0] if result.data else 0,
                    "out_octets": list(result.data.values())[1] if len(result.data) > 1 else 0,
                    "in_errors": list(result.data.values())[2] if len(result.data) > 2 else 0,
                    "out_errors": list(result.data.values())[3] if len(result.data) > 3 else 0,
                },
            )
        return result
