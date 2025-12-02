#!/bin/sh
# Traffic Generation Script for EVE-NG Linux Hosts
# Generates continuous traffic to simulate user activity

# All host IPs in the network
HOSTS="172.16.1.10 172.16.2.10 172.17.1.10 172.17.2.10 172.18.1.10 172.18.2.10"

# Gateway IPs (AGG routers)
GATEWAYS="172.16.1.1 172.16.2.1 172.17.1.1 172.17.2.1 172.18.1.1 172.18.2.1"

# Core router loopbacks (for backbone reachability)
CORE_LOOPBACKS="10.255.0.1 10.255.0.2 10.255.0.3 10.255.0.4 10.255.0.5"

# Get my IP
MY_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo "Starting traffic generation from $MY_IP"
echo "================================================"

# Function to generate ICMP traffic
generate_ping_traffic() {
    target=$1
    count=$2
    interval=$3

    if [ "$target" != "$MY_IP" ]; then
        ping -c $count -i $interval -W 1 $target > /dev/null 2>&1 &
    fi
}

# Function to generate TCP traffic using nc (netcat)
generate_tcp_traffic() {
    target=$1
    port=$2
    data_size=$3

    if [ "$target" != "$MY_IP" ]; then
        # Generate random data and send via TCP
        dd if=/dev/urandom bs=1024 count=$data_size 2>/dev/null | nc -w 1 $target $port > /dev/null 2>&1 &
    fi
}

# Function to generate UDP traffic
generate_udp_traffic() {
    target=$1
    port=$2

    if [ "$target" != "$MY_IP" ]; then
        # Send UDP packets
        echo "UDP traffic test from $MY_IP to $target" | nc -u -w 1 $target $port > /dev/null 2>&1 &
    fi
}

# Main traffic loop
while true; do
    echo "[$(date)] Generating traffic burst..."

    # 1. Ping all other hosts (simulate inter-site communication)
    for host in $HOSTS; do
        generate_ping_traffic $host 10 0.2
    done

    # 2. Ping all gateways (simulate local traffic)
    for gw in $GATEWAYS; do
        generate_ping_traffic $gw 5 0.5
    done

    # 3. Ping core loopbacks (simulate backbone traffic)
    for core in $CORE_LOOPBACKS; do
        generate_ping_traffic $core 3 1
    done

    # 4. Generate some larger ICMP packets (MTU testing)
    for host in $HOSTS; do
        if [ "$host" != "$MY_IP" ]; then
            ping -c 5 -s 1400 -W 1 $host > /dev/null 2>&1 &
        fi
    done

    # Wait before next burst
    sleep 30

    echo "[$(date)] Traffic burst complete. Waiting..."
done
