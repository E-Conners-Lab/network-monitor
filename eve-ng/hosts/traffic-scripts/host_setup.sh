#!/bin/sh
# Host Setup Script for EUNIV Network Lab
# Run this on each Linux host after connecting to the network

# Configuration - EDIT THESE VALUES for each host
# ================================================
# HOST1: MAIN-STUDENT  -> IP=172.16.1.10, GW=172.16.1.1
# HOST2: MAIN-STAFF    -> IP=172.16.2.10, GW=172.16.2.1
# HOST3: MED-STUDENT   -> IP=172.17.1.10, GW=172.17.1.1
# HOST4: MED-STAFF     -> IP=172.17.2.10, GW=172.17.2.1
# HOST5: RES-STUDENT   -> IP=172.18.1.10, GW=172.18.1.1
# HOST6: RES-STAFF     -> IP=172.18.2.10, GW=172.18.2.1

# Set these for your host:
HOST_IP=""
HOST_GW=""
HOST_NAME=""

# Auto-detect if not set
if [ -z "$HOST_IP" ]; then
    echo "Usage: $0 <host_number>"
    echo ""
    echo "Host numbers:"
    echo "  1 = MAIN-STUDENT (172.16.1.10)"
    echo "  2 = MAIN-STAFF   (172.16.2.10)"
    echo "  3 = MED-STUDENT  (172.17.1.10)"
    echo "  4 = MED-STAFF    (172.17.2.10)"
    echo "  5 = RES-STUDENT  (172.18.1.10)"
    echo "  6 = RES-STAFF    (172.18.2.10)"
    echo ""

    case "$1" in
        1) HOST_IP="172.16.1.10"; HOST_GW="172.16.1.1"; HOST_NAME="MAIN-STUDENT" ;;
        2) HOST_IP="172.16.2.10"; HOST_GW="172.16.2.1"; HOST_NAME="MAIN-STAFF" ;;
        3) HOST_IP="172.17.1.10"; HOST_GW="172.17.1.1"; HOST_NAME="MED-STUDENT" ;;
        4) HOST_IP="172.17.2.10"; HOST_GW="172.17.2.1"; HOST_NAME="MED-STAFF" ;;
        5) HOST_IP="172.18.1.10"; HOST_GW="172.18.1.1"; HOST_NAME="RES-STUDENT" ;;
        6) HOST_IP="172.18.2.10"; HOST_GW="172.18.2.1"; HOST_NAME="RES-STAFF" ;;
        *)
            echo "Invalid host number. Please specify 1-6."
            exit 1
            ;;
    esac
fi

echo "========================================"
echo "EUNIV Network Host Setup"
echo "========================================"
echo "Host Name: $HOST_NAME"
echo "IP Address: $HOST_IP"
echo "Gateway: $HOST_GW"
echo "========================================"

# Step 1: Configure network interface
echo ""
echo "[1/5] Configuring network interface..."

# Remove any existing IP
ip addr flush dev eth0 2>/dev/null

# Add new IP
ip addr add $HOST_IP/24 dev eth0
ip link set eth0 up

# Add default route
ip route del default 2>/dev/null
ip route add default via $HOST_GW

echo "  IP configured: $(ip -4 addr show eth0 | grep inet)"

# Step 2: Set hostname
echo ""
echo "[2/5] Setting hostname..."
hostname $HOST_NAME
echo $HOST_NAME > /etc/hostname
echo "  Hostname: $(hostname)"

# Step 3: Test gateway connectivity
echo ""
echo "[3/5] Testing gateway connectivity..."
if ping -c 3 -W 2 $HOST_GW > /dev/null 2>&1; then
    echo "  Gateway $HOST_GW: REACHABLE"
else
    echo "  Gateway $HOST_GW: UNREACHABLE"
    echo "  WARNING: Check EVE-NG cable connection!"
fi

# Step 4: Test cross-site connectivity
echo ""
echo "[4/5] Testing cross-site connectivity..."
OTHER_SITES="172.16.1.1 172.17.1.1 172.18.1.1"
for site in $OTHER_SITES; do
    if [ "$site" != "$HOST_GW" ]; then
        if ping -c 1 -W 2 $site > /dev/null 2>&1; then
            echo "  Site $site: REACHABLE"
        else
            echo "  Site $site: UNREACHABLE (routing may not be converged yet)"
        fi
    fi
done

# Step 5: Install required packages
echo ""
echo "[5/5] Installing traffic tools..."
if command -v apk > /dev/null 2>&1; then
    # Alpine Linux
    apk add --no-cache iperf3 curl python3 2>/dev/null
elif command -v apt-get > /dev/null 2>&1; then
    # Debian/Ubuntu
    apt-get update && apt-get install -y iperf3 curl python3 2>/dev/null
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To start traffic generation:"
echo "  ./traffic_gen.sh &     # Basic ping traffic"
echo "  ./iperf_traffic.sh &   # Bandwidth tests"
echo "  ./http_traffic.sh &    # HTTP simulation"
echo ""
echo "To verify connectivity to all hosts:"
echo "  for h in 172.16.1.10 172.16.2.10 172.17.1.10 172.17.2.10 172.18.1.10 172.18.2.10; do"
echo "    ping -c 1 -W 1 \$h && echo \"\$h OK\" || echo \"\$h FAIL\""
echo "  done"
echo ""
