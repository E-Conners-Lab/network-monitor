# EVE-NG Host Deployment Guide

This guide explains how to add Docker-based hosts to your EUNIV network lab in EVE-NG to simulate user traffic.

## Network Topology

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                        CORE NETWORK                          │
                    │   CORE1 ─── CORE2 ─── CORE3 ─── CORE4 ─── CORE5             │
                    │     │         │         │         │         │                │
                    │     └─────────┴────┬────┴─────────┴─────────┘                │
                    │                    │                                         │
                    └────────────────────┼─────────────────────────────────────────┘
                                         │
           ┌─────────────────────────────┼─────────────────────────────┐
           │                             │                             │
    ┌──────┴──────┐              ┌───────┴───────┐             ┌───────┴───────┐
    │  MAIN SITE  │              │   MED SITE    │             │   RES SITE    │
    │             │              │               │             │               │
    │  MAIN-AGG1  │              │   MED-AGG1    │             │   RES-AGG1    │
    │      │      │              │       │       │             │       │       │
    │  ┌───┴───┐  │              │   ┌───┴───┐   │             │   ┌───┴───┐   │
    │ EDGE1 EDGE2 │              │  EDGE1 EDGE2  │             │  EDGE1 EDGE2  │
    │  │       │  │              │   │       │   │             │   │       │   │
    │ HOST1 HOST2 │              │  HOST3 HOST4  │             │  HOST5 HOST6  │
    └─────────────┘              └───────────────┘             └───────────────┘
```

## Host IP Addressing

| Host | Site | Connected To | Interface | IP Address | Gateway | Subnet |
|------|------|--------------|-----------|------------|---------|--------|
| HOST1 | MAIN | MAIN-EDGE1 | Gi6 | 172.16.1.10/24 | 172.16.1.1 | STUDENT |
| HOST2 | MAIN | MAIN-EDGE2 | Gi6 | 172.16.2.10/24 | 172.16.2.1 | STAFF |
| HOST3 | MED | MED-EDGE1 | Gi6 | 172.17.1.10/24 | 172.17.1.1 | STUDENT |
| HOST4 | MED | MED-EDGE2 | Gi6 | 172.17.2.10/24 | 172.17.2.1 | STAFF |
| HOST5 | RES | RES-EDGE1 | Gi6 | 172.18.1.10/24 | 172.18.1.1 | STUDENT |
| HOST6 | RES | RES-EDGE2 | Gi6 | 172.18.2.10/24 | 172.18.2.1 | STAFF |

## Step 1: Add Linux Hosts in EVE-NG

1. In your EVE-NG lab, add 6 Linux nodes (use Alpine Linux or the built-in "linux" image)
2. Connect them to the Edge routers as follows:

| Host Node | Connect to | Router Interface |
|-----------|------------|------------------|
| HOST1-MAIN-STUDENT | MAIN-EDGE1 | Gi6 |
| HOST2-MAIN-STAFF | MAIN-EDGE2 | Gi6 |
| HOST3-MED-STUDENT | MED-EDGE1 | Gi6 |
| HOST4-MED-STAFF | MED-EDGE2 | Gi6 |
| HOST5-RES-STUDENT | RES-EDGE1 | Gi6 |
| HOST6-RES-STAFF | RES-EDGE2 | Gi6 |

## Step 2: Configure Edge Router Interfaces

Apply the following configuration to each Edge router.

### MAIN-EDGE1 Configuration
```
interface GigabitEthernet6
 description HOST-STUDENT-NET
 ip address 172.16.1.1 255.255.255.0
 no shutdown
```

### MAIN-EDGE2 Configuration
```
interface GigabitEthernet6
 description HOST-STAFF-NET
 ip address 172.16.2.1 255.255.255.0
 no shutdown
```

### MED-EDGE1 Configuration
```
interface GigabitEthernet6
 description HOST-STUDENT-NET
 ip address 172.17.1.1 255.255.255.0
 no shutdown
```

### MED-EDGE2 Configuration
```
interface GigabitEthernet6
 description HOST-STAFF-NET
 ip address 172.17.2.1 255.255.255.0
 no shutdown
```

### RES-EDGE1 Configuration
```
interface GigabitEthernet6
 description HOST-STUDENT-NET
 ip address 172.18.1.1 255.255.255.0
 no shutdown
```

### RES-EDGE2 Configuration
```
interface GigabitEthernet6
 description HOST-STAFF-NET
 ip address 172.18.2.1 255.255.255.0
 no shutdown
```

## Step 3: Configure Hosts

### HOST1 (MAIN-STUDENT)
```bash
# Set IP address
ip addr add 172.16.1.10/24 dev eth0
ip route add default via 172.16.1.1

# Test connectivity
ping -c 3 172.16.1.1
```

### HOST2 (MAIN-STAFF)
```bash
ip addr add 172.16.2.10/24 dev eth0
ip route add default via 172.16.2.1
```

### HOST3 (MED-STUDENT)
```bash
ip addr add 172.17.1.10/24 dev eth0
ip route add default via 172.17.1.1
```

### HOST4 (MED-STAFF)
```bash
ip addr add 172.17.2.10/24 dev eth0
ip route add default via 172.17.2.1
```

### HOST5 (RES-STUDENT)
```bash
ip addr add 172.18.1.10/24 dev eth0
ip route add default via 172.18.1.1
```

### HOST6 (RES-STAFF)
```bash
ip addr add 172.18.2.10/24 dev eth0
ip route add default via 172.18.2.1
```

## Step 4: Add OSPF Routes on Edge Routers

Add the host subnets to OSPF so they're reachable across sites:

### MAIN-EDGE1
```
router ospf 1
 network 172.16.1.0 0.0.0.255 area 0
```

### MAIN-EDGE2
```
router ospf 1
 network 172.16.2.0 0.0.0.255 area 0
```

### MED-EDGE1
```
router ospf 1
 network 172.17.1.0 0.0.0.255 area 0
```

### MED-EDGE2
```
router ospf 1
 network 172.17.2.0 0.0.0.255 area 0
```

### RES-EDGE1
```
router ospf 1
 network 172.18.1.0 0.0.0.255 area 0
```

### RES-EDGE2
```
router ospf 1
 network 172.18.2.0 0.0.0.255 area 0
```

## Step 5: Run Traffic Generation Scripts

On each host, use the automated setup script:

```bash
# Copy scripts to host (or paste content directly)
# Run setup script with host number (1-6)
./host_setup.sh 1   # For HOST1
./host_setup.sh 2   # For HOST2
# ... etc
```

Or use the combined traffic generator after manual IP setup:

```bash
# Start all traffic types
./run_all_traffic.sh
```

### Available Scripts

| Script | Purpose |
|--------|---------|
| `host_setup.sh` | Full host setup (IP, hostname, tests) |
| `run_all_traffic.sh` | Combined traffic generator |
| `traffic_gen.sh` | ICMP ping traffic only |
| `iperf_traffic.sh` | Bandwidth tests (requires iperf3) |
| `http_traffic.sh` | HTTP simulation |

## Step 6: Verify Connectivity

### From Any Host
```bash
# Test all hosts
for h in 172.16.1.10 172.16.2.10 172.17.1.10 172.17.2.10 172.18.1.10 172.18.2.10; do
  ping -c 1 -W 1 $h && echo "$h OK" || echo "$h FAIL"
done

# Test core loopbacks
for lb in 10.255.0.11 10.255.0.21 10.255.0.31; do
  ping -c 1 -W 1 $lb && echo "$lb OK" || echo "$lb FAIL"
done
```

### From Network Monitor
Use the API to verify hosts are generating traffic:
```bash
# Check interface metrics on Edge routers
curl -s http://localhost:8080/api/metrics/device/MAIN-EDGE1/latest
```

## Troubleshooting

### Host Can't Reach Gateway
1. Verify cable is connected in EVE-NG (link should show green)
2. Check router interface is up: `show ip interface brief | inc Gi6`
3. Verify IP configuration: `ip addr show eth0`

### Cross-Site Traffic Not Working
1. Verify OSPF is advertising host subnets: `show ip route ospf | inc 172`
2. Check OSPF neighbor status on Edge: `show ip ospf neighbor`
3. Trace the path: `traceroute 172.17.1.10` (from MAIN to MED)

### Traffic Not Showing in Monitor
1. Ensure SNMP polling is running: check Celery worker logs
2. Verify interface counters incrementing: `show interface Gi6 | inc packets`
3. Wait for next polling cycle (default 30 seconds)
