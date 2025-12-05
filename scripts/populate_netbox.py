#!/usr/bin/env python3
"""Populate NetBox with E-University devices."""

import os
import sys

import pynetbox

# NetBox connection
NETBOX_URL = os.environ.get("NETBOX_URL", "http://localhost:8000")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")

# E-University Device Inventory
DEVICES = [
    {"name": "EUNIV-CORE1", "ip": "192.168.68.200", "role": "core", "loopback": "10.255.0.1"},
    {"name": "EUNIV-CORE2", "ip": "192.168.68.202", "role": "core", "loopback": "10.255.0.2"},
    {"name": "EUNIV-CORE3", "ip": "192.168.68.203", "role": "core", "loopback": "10.255.0.3"},
    {"name": "EUNIV-CORE4", "ip": "192.168.68.204", "role": "core", "loopback": "10.255.0.4"},
    {"name": "EUNIV-CORE5", "ip": "192.168.68.205", "role": "core", "loopback": "10.255.0.5"},
    {"name": "EUNIV-INET-GW1", "ip": "192.168.68.206", "role": "gateway", "loopback": "10.255.0.101"},
    {"name": "EUNIV-INET-GW2", "ip": "192.168.68.207", "role": "gateway", "loopback": "10.255.0.102"},
    {"name": "EUNIV-MAIN-AGG1", "ip": "192.168.68.208", "role": "aggregation", "loopback": "10.255.1.1"},
    {"name": "EUNIV-MAIN-EDGE1", "ip": "192.168.68.209", "role": "edge", "loopback": "10.255.1.11"},
    {"name": "EUNIV-MAIN-EDGE2", "ip": "192.168.68.210", "role": "edge", "loopback": "10.255.1.12"},
    {"name": "EUNIV-MED-AGG1", "ip": "192.168.68.211", "role": "aggregation", "loopback": "10.255.2.1"},
    {"name": "EUNIV-MED-EDGE1", "ip": "192.168.68.212", "role": "edge", "loopback": "10.255.2.11"},
    {"name": "EUNIV-MED-EDGE2", "ip": "192.168.68.213", "role": "edge", "loopback": "10.255.2.12"},
    {"name": "EUNIV-RES-AGG1", "ip": "192.168.68.214", "role": "aggregation", "loopback": "10.255.3.1"},
    {"name": "EUNIV-RES-EDGE1", "ip": "192.168.68.215", "role": "edge", "loopback": "10.255.3.11"},
    {"name": "EUNIV-RES-EDGE2", "ip": "192.168.68.216", "role": "edge", "loopback": "10.255.3.12"},
]


def main():
    if not NETBOX_TOKEN:
        print("ERROR: NETBOX_TOKEN environment variable not set")
        print("\nTo create a token:")
        print("1. Log into NetBox at http://localhost:8000")
        print("2. Go to Admin -> API Tokens")
        print("3. Create a new token with write permissions")
        print("4. Run: export NETBOX_TOKEN='your-token-here'")
        sys.exit(1)

    print(f"Connecting to NetBox at {NETBOX_URL}...")
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

    # Test connection
    try:
        status = nb.status()
        print(f"Connected to NetBox {status.get('netbox-version', 'unknown')}")
    except Exception as e:
        print(f"ERROR: Could not connect to NetBox: {e}")
        sys.exit(1)

    # Step 1: Create or get site
    print("\n=== Setting up Site ===")
    site_slug = "euniv-datacenter"
    site = nb.dcim.sites.get(slug=site_slug)
    if not site:
        site = nb.dcim.sites.create(
            name="E-University Datacenter",
            slug=site_slug,
            status="active",
        )
        print(f"  Created site: {site.name}")
    else:
        print(f"  Site exists: {site.name}")

    # Step 2: Create or get manufacturer
    print("\n=== Setting up Manufacturer ===")
    manufacturer = nb.dcim.manufacturers.get(slug="cisco")
    if not manufacturer:
        manufacturer = nb.dcim.manufacturers.create(
            name="Cisco",
            slug="cisco",
        )
        print(f"  Created manufacturer: {manufacturer.name}")
    else:
        print(f"  Manufacturer exists: {manufacturer.name}")

    # Step 3: Create or get device type
    print("\n=== Setting up Device Type ===")
    device_type = nb.dcim.device_types.get(model="CSR1000V")
    if not device_type:
        device_type = nb.dcim.device_types.create(
            manufacturer=manufacturer.id,
            model="CSR1000V",
            slug="csr1000v",
            u_height=0,  # Virtual device
            is_full_depth=False,
        )
        print(f"  Created device type: {device_type.model}")
    else:
        print(f"  Device type exists: {device_type.model}")

    # Step 4: Create device roles
    print("\n=== Setting up Device Roles ===")
    roles = {}
    for role_slug in ["router", "core", "gateway", "aggregation", "edge"]:
        role = nb.dcim.device_roles.get(slug=role_slug)
        if not role:
            role = nb.dcim.device_roles.create(
                name=role_slug.title(),
                slug=role_slug,
                color="9e9e9e",  # Grey
                vm_role=True,
            )
            print(f"  Created role: {role.name}")
        else:
            print(f"  Role exists: {role.name}")
        roles[role_slug] = role

    # Step 5: Create devices and assign IPs
    print("\n=== Creating/Updating Devices ===")
    created = 0
    updated = 0

    for device_info in DEVICES:
        # Check if device exists
        device = nb.dcim.devices.get(name=device_info["name"])

        if not device:
            # Create device
            try:
                device = nb.dcim.devices.create(
                    name=device_info["name"],
                    device_type=device_type.id,
                    role=roles[device_info["role"]].id,
                    site=site.id,
                    status="active",
                    comments=f"Loopback: {device_info['loopback']}",
                )
                print(f"  Created device: {device.name}")
                created += 1
            except Exception as e:
                print(f"  ERROR creating {device_info['name']}: {e}")
                continue
        else:
            print(f"  Device exists: {device.name}")

        # Create or get management interface
        try:
            mgmt_iface = nb.dcim.interfaces.get(device_id=device.id, name="GigabitEthernet1")
            if not mgmt_iface:
                mgmt_iface = nb.dcim.interfaces.create(
                    device=device.id,
                    name="GigabitEthernet1",
                    type="1000base-t",
                    description="Management Interface",
                )
                print("    Created interface: GigabitEthernet1")

            # Create or get IP address
            ip = nb.ipam.ip_addresses.get(address=f"{device_info['ip']}/24")
            if not ip:
                ip = nb.ipam.ip_addresses.create(
                    address=f"{device_info['ip']}/24",
                    status="active",
                    description=f"Management IP for {device_info['name']}",
                    assigned_object_type="dcim.interface",
                    assigned_object_id=mgmt_iface.id,
                )
                print(f"    Created IP: {device_info['ip']}/24")
            elif not ip.assigned_object_id:
                # Assign existing IP to interface
                ip.assigned_object_type = "dcim.interface"
                ip.assigned_object_id = mgmt_iface.id
                ip.save()
                print(f"    Assigned IP: {device_info['ip']}/24")

            # Set as primary IP
            if not device.primary_ip4 or device.primary_ip4.id != ip.id:
                device.primary_ip4 = ip.id
                device.save()
                print(f"    Set primary IP: {device_info['ip']}")
                updated += 1

        except Exception as e:
            print(f"    ERROR setting up IP for {device_info['name']}: {e}")

    print(f"\n{'='*50}")
    print("NetBox population complete!")
    print(f"  Created: {created} devices")
    print(f"  Updated: {updated} devices (IPs assigned)")
    print(f"  Total: {len(DEVICES)} devices")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
