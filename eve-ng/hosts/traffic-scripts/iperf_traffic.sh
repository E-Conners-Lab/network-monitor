#!/bin/sh
# iPerf Traffic Generation Script
# Generates bandwidth traffic between sites

# Site endpoints for iperf tests
# Format: "IP:ROLE" where role helps identify the host
ENDPOINTS="
172.16.1.10:MAIN-STUDENT
172.16.2.10:MAIN-STAFF
172.17.1.10:MED-STUDENT
172.17.2.10:MED-STAFF
172.18.1.10:RES-STUDENT
172.18.2.10:RES-STAFF
"

MY_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
IPERF_PORT=5001

echo "iPerf Traffic Generator"
echo "======================="
echo "My IP: $MY_IP"

# Check if iperf3 is installed
if ! command -v iperf3 > /dev/null 2>&1; then
    echo "Installing iperf3..."
    apk add --no-cache iperf3 2>/dev/null || apt-get install -y iperf3 2>/dev/null || yum install -y iperf3 2>/dev/null
fi

# Start iperf server in background
echo "Starting iperf3 server on port $IPERF_PORT..."
iperf3 -s -p $IPERF_PORT -D

# Wait for server to start
sleep 2

# Client traffic generation loop
while true; do
    for endpoint in $ENDPOINTS; do
        ip=$(echo $endpoint | cut -d: -f1)
        role=$(echo $endpoint | cut -d: -f2)

        if [ "$ip" != "$MY_IP" ]; then
            echo "[$(date)] Testing bandwidth to $role ($ip)..."

            # TCP test - 10 second duration, report every 2 seconds
            iperf3 -c $ip -p $IPERF_PORT -t 10 -i 2 --connect-timeout 3000 2>/dev/null &

            # Small delay between tests
            sleep 15
        fi
    done

    echo "[$(date)] Completed round of bandwidth tests. Waiting 60s..."
    sleep 60
done
