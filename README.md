# Network Monitor

Enterprise network monitoring application with automated remediation for Cisco devices. Built with FastAPI, React, Celery, and PostgreSQL.

## Features

- **Real-time Device Monitoring**: Poll routers, switches, and firewalls via SNMP and SSH
- **BGP/OSPF Routing Monitoring**: Track neighbor states, prefixes, and protocol health using pyATS/Genie
- **Interface Metrics**: Monitor bandwidth utilization (bps), errors, and operational status
- **Network Validation Tests**: Run comprehensive pyATS-based tests (connectivity, BGP, OSPF, interfaces, routing tables)
- **NetBox Integration**: Sync device inventory from NetBox DCIM
- **Automated Alerting**: Generate alerts for device unreachability, high CPU/memory, interface errors, BGP/OSPF neighbor issues
- **Auto-Remediation**: Intelligent remediation that maps alerts to fixes (clear BGP, enable interfaces, etc.)
- **OS Version Collection**: Automatically collect and display IOS/IOS-XE/NX-OS versions from devices
- **React Web Dashboard**: Modern UI with device details, metrics charts, routing tables, and test results
- **REST API**: Full-featured API with Swagger documentation
- **WebSocket Events**: Real-time streaming of device status, metrics, alerts, and remediation events

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React UI      │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   (Port 3000)   │     │   (Port 8080)   │     │   (Port 5432)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   Celery        │
                        │   Workers       │
                        └─────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │  SNMP    │    │  SSH     │    │  NetBox  │
        │  Polling │    │  pyATS   │    │  Sync    │
        └──────────┘    └──────────┘    └──────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Network devices with SNMP enabled (community: `public`)
- SSH access to devices for routing monitoring

### 1. Clone and Configure

```bash
git clone https://github.com/yourusername/network-monitor.git
cd network-monitor

# Copy environment template
cp .env.example .env
```

### 2. Start Services

```bash
# Start all containers
docker-compose up -d

# Check status
docker-compose ps
```

### 3. Initialize Database

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Create admin user (admin/admin)
docker-compose exec api python scripts/init_db.py
```

### 4. Access the Application

| Service | URL | Credentials |
|---------|-----|-------------|
| Web UI | http://localhost:3000 | admin/admin |
| API Docs | http://localhost:8080/docs | - |
| NetBox | http://localhost:8000 | admin/admin |

## Device Requirements

### SNMP Configuration (Cisco IOS/IOS-XE)

```
snmp-server community public RO
snmp-server location Building-A
snmp-server contact netops@company.com
```

### SSH Configuration (for pyATS routing monitoring)

```
hostname ROUTER-NAME
ip domain-name lab.local
crypto key generate rsa modulus 2048
username netmon privilege 15 secret YOUR_PASSWORD
line vty 0 4
 login local
 transport input ssh
```

## Services

### API (FastAPI)
- REST API for all operations
- JWT authentication
- Swagger UI at `/docs`

### Celery Worker
- SNMP polling (every 30 seconds) with parallel execution (5 concurrent max)
- Routing protocol polling via pyATS (every 5 minutes)
- Alert processing
- Fast failure detection with early exit (skips SNMP if ping fails)

### Celery Beat
- Scheduled task orchestration
- Periodic polling triggers

### Frontend (React)
- Device dashboard with status overview and active alerts
- Device detail pages with metrics charts and interface traffic (bps)
- Routing tab showing BGP/OSPF neighbors with state indicators
- Alert management with auto-remediate buttons
- Network Tests page for running pyATS validation suites
- Remediation page with playbook execution and history

## API Endpoints

### Health & Info
- `GET /health` - Health check endpoint
- `GET /` - API info and version

### Authentication
- `POST /api/auth/token` - Login
- `POST /api/auth/register` - Register new user
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Current user

### Devices
- `GET /api/devices` - List devices
- `POST /api/devices` - Create device
- `GET /api/devices/{id}` - Get device
- `PUT /api/devices/{id}` - Update device
- `DELETE /api/devices/{id}` - Delete device
- `POST /api/devices/{id}/check` - Poll single device
- `POST /api/devices/check-all` - Poll all devices (bulk operation)

### Metrics
- `GET /api/metrics` - List metrics
- `POST /api/metrics` - Create metric
- `GET /api/metrics/device/{id}/latest` - Latest metrics
- `GET /api/metrics/device/{id}/summary` - Metric summaries (min/max/avg)
- `GET /api/metrics/device/{id}/routing` - BGP/OSPF neighbors

### Alerts
- `GET /api/alerts` - List alerts
- `POST /api/alerts` - Create alert
- `GET /api/alerts/{id}` - Get single alert
- `PUT /api/alerts/{id}` - Update alert
- `GET /api/alerts/active` - Active alerts
- `POST /api/alerts/{id}/acknowledge` - Acknowledge alert
- `POST /api/alerts/{id}/resolve` - Resolve alert

### Remediation
- `GET /api/remediation/playbooks` - List available playbooks
- `GET /api/remediation/logs` - Remediation history
- `GET /api/remediation/logs/{id}` - Get specific remediation log
- `POST /api/remediation/alerts/{id}/auto-remediate` - Auto-remediate an alert
- `POST /api/remediation/alerts/{id}/send-webhook` - Send webhook notification for alert
- `POST /api/remediation/devices/{id}/interface/enable` - Enable interface
- `POST /api/remediation/devices/{id}/bgp/clear` - Clear BGP neighbor
- `POST /api/remediation/devices/{id}/caches/clear` - Clear device caches

### Network Tests
- `POST /api/tests/run` - Run tests with specified test_type parameter
- `POST /api/tests/run/quick` - Run quick health check (connectivity, BGP, OSPF)
- `POST /api/tests/run/full` - Run full validation (+ interfaces, routing tables, paths)
- `POST /api/tests/devices/{id}/run` - Run tests on single device
- `GET /api/tests/status/{task_id}` - Get test results

### NetBox Integration
- `GET /api/devices/netbox/status` - NetBox connection status
- `GET /api/devices/netbox/devices` - Preview devices from NetBox before sync
- `POST /api/devices/netbox/sync` - Sync devices from NetBox (preserves local `is_active` overrides)

### OS Version Collection
- `POST /api/devices/collect-os-versions` - Collect OS versions from all devices via SSH
- `POST /api/devices/sync-os-to-netbox` - Sync OS versions to NetBox (sets platform and software_version custom field)

### WebSocket
- `WS /ws/events` - Real-time event streaming (device status, metrics, alerts, remediation)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | - |
| `NETBOX_URL` | NetBox API URL | - |
| `NETBOX_TOKEN` | NetBox API token | - |
| `SECRET_KEY` | JWT secret key | - |
| `SNMP_COMMUNITY` | Default SNMP community | `public` |
| `SSH_USERNAME` | Default SSH username | - |
| `SSH_PASSWORD` | Default SSH password | - |

### Device Credentials

SSH credentials for routing monitoring can be configured in `.env`:

```env
SSH_USERNAME=netmon
SSH_PASSWORD=your_password
```

## Metrics Collected

### SNMP Metrics
- CPU Utilization (%)
- Memory Utilization (%)
- Interface In/Out Octets (bytes)
- Interface In/Out Rate (bps) - calculated from octet counters
- Interface In/Out Errors
- Interface Status (up/down)
- Ping Latency (ms)
- Ping Packet Loss (%)

### Routing Metrics (via pyATS)
- BGP Neighbor State (established/idle/active)
- BGP Prefixes Received
- BGP Uptime
- OSPF Neighbor State (full/2way/down)
- OSPF Interface/Area

### Device Info (via SSH)
- OS Version (IOS, IOS-XE, NX-OS)

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/
```

### Rebuild Frontend

```bash
docker-compose build frontend
docker-compose up -d frontend
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery-worker
```

## EVE-NG Host Deployment

The project includes traffic generation scripts for adding Linux hosts to your EVE-NG lab.

See `eve-ng/hosts/README.md` for complete deployment guide.

### Host Configuration

| Host | Site | Edge Router | IP Address |
|------|------|-------------|------------|
| HOST1 | MAIN | MAIN-EDGE1 | 172.16.1.10/24 |
| HOST2 | MAIN | MAIN-EDGE2 | 172.16.2.10/24 |
| HOST3 | MED | MED-EDGE1 | 172.17.1.10/24 |
| HOST4 | MED | MED-EDGE2 | 172.17.2.10/24 |
| HOST5 | RES | RES-EDGE1 | 172.18.1.10/24 |
| HOST6 | RES | RES-EDGE2 | 172.18.2.10/24 |

### Traffic Scripts

| Script | Purpose |
|--------|---------|
| `host_setup.sh` | Configure host IP and test connectivity |
| `run_all_traffic.sh` | Generate ICMP, TCP, and bandwidth traffic |

## Troubleshooting

### Device Not Responding
1. Verify SNMP community string
2. Check firewall rules for UDP 161
3. Test with: `snmpwalk -v2c -c public <device_ip> sysDescr`

### Routing Data Not Showing
1. Verify SSH credentials in `.env`
2. Check device supports SSH and has required privileges
3. View celery logs: `docker-compose logs celery-worker`

### Database Issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres
docker-compose exec api alembic upgrade head
```

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Celery
- **Frontend**: React 18, TailwindCSS, Recharts
- **Database**: PostgreSQL 16, Redis 7
- **Network**: pyATS/Genie, PySNMP, Netmiko
- **Infrastructure**: Docker, Docker Compose

## License

MIT
