#!/usr/bin/env python3
"""Import E-University network devices into Network Monitor."""

import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

from src.models.base import AsyncSessionLocal
from src.models.device import Device, DeviceType

# E-University Device Inventory from design document
DEVICES = [
    {"name": "EUNIV-CORE1", "ip": "192.168.68.200", "role": "Core / Route Reflector", "loopback": "10.255.0.1"},
    {"name": "EUNIV-CORE2", "ip": "192.168.68.202", "role": "Core / Route Reflector", "loopback": "10.255.0.2"},
    {"name": "EUNIV-CORE3", "ip": "192.168.68.203", "role": "Core / P Router", "loopback": "10.255.0.3"},
    {"name": "EUNIV-CORE4", "ip": "192.168.68.204", "role": "Core / P Router", "loopback": "10.255.0.4"},
    {"name": "EUNIV-CORE5", "ip": "192.168.68.205", "role": "Core / Route Reflector", "loopback": "10.255.0.5"},
    {"name": "EUNIV-INET-GW1", "ip": "192.168.68.206", "role": "Internet Gateway", "loopback": "10.255.0.101"},
    {"name": "EUNIV-INET-GW2", "ip": "192.168.68.207", "role": "Internet Gateway", "loopback": "10.255.0.102"},
    {"name": "EUNIV-MAIN-AGG1", "ip": "192.168.68.208", "role": "Main Campus Aggregation", "loopback": "10.255.1.1"},
    {"name": "EUNIV-MAIN-EDGE1", "ip": "192.168.68.209", "role": "Main Campus Edge", "loopback": "10.255.1.11"},
    {"name": "EUNIV-MAIN-EDGE2", "ip": "192.168.68.210", "role": "Main Campus Edge", "loopback": "10.255.1.12"},
    {"name": "EUNIV-MED-AGG1", "ip": "192.168.68.211", "role": "Medical Campus Aggregation", "loopback": "10.255.2.1"},
    {"name": "EUNIV-MED-EDGE1", "ip": "192.168.68.212", "role": "Medical Campus Edge", "loopback": "10.255.2.11"},
    {"name": "EUNIV-MED-EDGE2", "ip": "192.168.68.213", "role": "Medical Campus Edge", "loopback": "10.255.2.12"},
    {"name": "EUNIV-RES-AGG1", "ip": "192.168.68.214", "role": "Research Campus Aggregation", "loopback": "10.255.3.1"},
    {"name": "EUNIV-RES-EDGE1", "ip": "192.168.68.215", "role": "Research Campus Edge", "loopback": "10.255.3.11"},
    {"name": "EUNIV-RES-EDGE2", "ip": "192.168.68.216", "role": "Research Campus Edge", "loopback": "10.255.3.12"},
]

# SNMP settings
SNMP_COMMUNITY = "euniv-mon-ro"


async def import_devices():
    """Import all E-University devices."""
    async with AsyncSessionLocal() as session:
        added = 0
        skipped = 0

        for device_info in DEVICES:
            # Check if device already exists by name
            result = await session.execute(
                select(Device).where(Device.name == device_info["name"])
            )
            if result.scalar_one_or_none():
                print(f"  Skipping {device_info['name']} (already exists)")
                skipped += 1
                continue

            # Create new device
            device = Device(
                name=device_info["name"],
                hostname=device_info["name"],
                ip_address=device_info["ip"],
                device_type=DeviceType.ROUTER,
                vendor="cisco",
                model="CSR1000V",
                description=f"{device_info['role']} - Loopback: {device_info['loopback']}",
                snmp_community=SNMP_COMMUNITY,
                snmp_version=2,
                is_active=True,
                is_reachable=False,  # Will be updated on first health check
                tags={
                    "role": device_info["role"],
                    "loopback": device_info["loopback"],
                    "ssh_username": "admin",
                    "ssh_password": "Pass2885!",
                },
            )
            session.add(device)
            print(f"  Adding {device_info['name']} ({device_info['ip']})")
            added += 1

        await session.commit()

        print(f"\n{'='*50}")
        print("Import complete!")
        print(f"  Added: {added} devices")
        print(f"  Skipped: {skipped} devices (already existed)")
        print(f"  Total: {len(DEVICES)} devices")
        print(f"{'='*50}")


if __name__ == "__main__":
    print("E-University Network Device Import")
    print("="*50)
    print(f"Importing {len(DEVICES)} CSR1000v devices...")
    print()
    asyncio.run(import_devices())
