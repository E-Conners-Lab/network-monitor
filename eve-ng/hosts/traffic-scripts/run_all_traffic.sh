#!/bin/sh
# Combined Traffic Generator for EUNIV Network Lab
# Runs all traffic types in background with summary output

echo "========================================"
echo "EUNIV Network Traffic Generator"
echo "========================================"
echo "Starting all traffic generation services..."
echo ""

# Get current host info
MY_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP 'inet \K[\d.]+' || hostname -I | awk '{print $1}')
MY_NAME=$(hostname)

echo "Host: $MY_NAME ($MY_IP)"
echo ""

# All host IPs
ALL_HOSTS="172.16.1.10 172.16.2.10 172.17.1.10 172.17.2.10 172.18.1.10 172.18.2.10"
# Core loopbacks for backbone testing
LOOPBACKS="10.255.0.1 10.255.0.2 10.255.0.11 10.255.0.12 10.255.0.21 10.255.0.22 10.255.0.31 10.255.0.32"

# Function to generate ping traffic
generate_ping_traffic() {
    while true; do
        for host in $ALL_HOSTS; do
            if [ "$host" != "$MY_IP" ]; then
                ping -c 2 -W 1 $host > /dev/null 2>&1
            fi
        done
        # Also ping core loopbacks
        for lb in $LOOPBACKS; do
            ping -c 1 -W 1 $lb > /dev/null 2>&1
        done
        sleep 10
    done
}

# Function to generate TCP traffic (simulated HTTP)
generate_tcp_traffic() {
    while true; do
        for host in $ALL_HOSTS; do
            if [ "$host" != "$MY_IP" ]; then
                # Try to connect on common ports
                timeout 2 sh -c "echo 'GET / HTTP/1.0\r\n\r\n' | nc $host 80" > /dev/null 2>&1
                timeout 2 sh -c "echo 'GET / HTTP/1.0\r\n\r\n' | nc $host 8080" > /dev/null 2>&1
            fi
        done
        sleep 30
    done
}

# Function for iperf bandwidth tests (if iperf3 available)
generate_iperf_traffic() {
    if ! command -v iperf3 > /dev/null 2>&1; then
        echo "iperf3 not available, skipping bandwidth tests"
        return
    fi

    while true; do
        for host in $ALL_HOSTS; do
            if [ "$host" != "$MY_IP" ]; then
                # Short bandwidth test
                iperf3 -c $host -t 5 -P 2 > /dev/null 2>&1
            fi
        done
        sleep 120
    done
}

# Function to show traffic statistics
show_stats() {
    echo ""
    echo "=== Connectivity Status ==="
    for host in $ALL_HOSTS; do
        if [ "$host" != "$MY_IP" ]; then
            if ping -c 1 -W 1 $host > /dev/null 2>&1; then
                echo "  $host: REACHABLE"
            else
                echo "  $host: UNREACHABLE"
            fi
        else
            echo "  $host: (self)"
        fi
    done
    echo ""
}

# Show initial connectivity
show_stats

# Start traffic generators in background
echo "Starting traffic generators..."
generate_ping_traffic &
PING_PID=$!
echo "  ICMP traffic: PID $PING_PID"

generate_tcp_traffic &
TCP_PID=$!
echo "  TCP traffic: PID $TCP_PID"

generate_iperf_traffic &
IPERF_PID=$!
echo "  Bandwidth tests: PID $IPERF_PID"

echo ""
echo "========================================"
echo "Traffic generation running!"
echo "========================================"
echo ""
echo "To stop: kill $PING_PID $TCP_PID $IPERF_PID"
echo "Or run: pkill -f 'run_all_traffic'"
echo ""
echo "Showing stats every 60 seconds..."
echo "(Press Ctrl+C to stop)"
echo ""

# Main loop - show stats periodically
trap "kill $PING_PID $TCP_PID $IPERF_PID 2>/dev/null; exit 0" INT TERM

while true; do
    sleep 60
    show_stats
done
