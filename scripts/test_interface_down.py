#!/usr/bin/env python3
"""
Test script to simulate an interface failure for remediation testing.

This script will:
1. Connect to a device
2. Shut down a non-critical interface
3. Wait for the monitoring system to detect the outage
4. You can then test remediation from the web UI

Usage:
    python scripts/test_interface_down.py [--device DEVICE_IP] [--interface INTERFACE]

Default: Shuts down GigabitEthernet3 on CORE2 (192.168.68.202)
"""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description='Test interface down scenario')
    parser.add_argument('--device', default='192.168.68.202', help='Device IP (default: CORE2)')
    parser.add_argument('--interface', default='GigabitEthernet3', help='Interface to shut down')
    parser.add_argument('--restore', action='store_true', help='Restore the interface instead of shutting it down')
    args = parser.parse_args()

    try:
        from netmiko import ConnectHandler
    except ImportError:
        print("Error: netmiko not installed. Run: pip install netmiko")
        sys.exit(1)

    device = {
        'device_type': 'cisco_ios',
        'host': args.device,
        'username': 'admin',
        'password': 'Pass2885!',
        'timeout': 60,
    }

    print(f"Connecting to {args.device}...")

    try:
        conn = ConnectHandler(**device)
        hostname = conn.find_prompt().replace('#', '').replace('>', '')
        print(f"Connected to {hostname}")

        # Show current interface status
        print(f"\nCurrent status of {args.interface}:")
        output = conn.send_command(f'show interface {args.interface} | include line protocol')
        print(f"  {output.strip()}")

        if args.restore:
            # Bring interface back up
            print(f"\nRestoring {args.interface}...")
            config_commands = [
                f'interface {args.interface}',
                'no shutdown'
            ]
            conn.send_config_set(config_commands)
            print("Interface restored!")
        else:
            # Shut down the interface
            print(f"\nShutting down {args.interface}...")
            config_commands = [
                f'interface {args.interface}',
                'shutdown'
            ]
            conn.send_config_set(config_commands)
            print("Interface shut down!")

        # Show new status
        time.sleep(2)
        print(f"\nNew status of {args.interface}:")
        output = conn.send_command(f'show interface {args.interface} | include line protocol')
        print(f"  {output.strip()}")

        conn.disconnect()

        if not args.restore:
            print("\n" + "="*60)
            print("TEST SCENARIO ACTIVE")
            print("="*60)
            print(f"Interface {args.interface} on {hostname} is now DOWN")
            print("\nWhat to do next:")
            print("1. Wait 30-60 seconds for monitoring to detect the outage")
            print("2. Check the Alerts page in the web UI")
            print("3. Try the 'Auto-Remediate' button or manual remediation")
            print(f"\nTo manually restore: python scripts/test_interface_down.py --restore --device {args.device} --interface {args.interface}")
            print("="*60)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
