# Network Monitor

Enterprise network monitoring application with automated remediation for Cisco devices. Built with FastAPI, React, Celery, and PostgreSQL.

## Features

- **Real-time Device Monitoring**: Poll routers, switches, and firewalls via SNMP and SSH
- **BGP/OSPF Routing Monitoring**: Track neighbor states, prefixes, and protocol health using pyATS/Genie
- **Interface Metrics**: Monitor bandwidth utilization, errors, and operational status
- **NetBox Integration**: Sync device inventory from NetBox DCIM
- **Automated Alerting**: Generate alerts for device unreachability, high CPU/memory, interface errors
- **Remediation Playbooks**: Execute automated fixes for common issues
- **React Web Dashboard**: Modern UI with device details, metrics charts, and routing tables
- **REST API**: Full-featured API with Swagger documentation

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
- SNMP polling (every 30 seconds)
- Routing protocol polling via pyATS (every 5 minutes)
- Alert processing

### Celery Beat
- Scheduled task orchestration
- Periodic polling triggers

### Frontend (React)
- Device dashboard with status overview
- Device detail pages with metrics charts
- Routing tab showing BGP/OSPF neighbors
- Alert management

## API Endpoints

### Authentication
- `POST /api/auth/token` - Login
- `GET /api/auth/me` - Current user

### Devices
- `GET /api/devices` - List devices
- `POST /api/devices` - Create device
- `GET /api/devices/{id}` - Get device
- `POST /api/devices/{id}/check` - Poll device

### Metrics
- `GET /api/metrics` - List metrics
- `GET /api/metrics/device/{id}/latest` - Latest metrics
- `GET /api/metrics/device/{id}/routing` - BGP/OSPF neighbors

### Alerts
- `GET /api/alerts` - List alerts
- `GET /api/alerts/active` - Active alerts
- `POST /api/alerts/{id}/acknowledge` - Acknowledge alert

### NetBox Integration
- `GET /api/devices/netbox/status` - NetBox connection status
- `POST /api/devices/netbox/sync` - Sync devices from NetBox

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
- CPU Utilization
- Memory Utilization
- Interface In/Out Octets
- Interface In/Out Errors
- Interface Status (up/down)

### Routing Metrics (via pyATS)
- BGP Neighbor State (established/idle)
- BGP Prefixes Received
- BGP Uptime
- OSPF Neighbor State
- OSPF Interface/Area

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
