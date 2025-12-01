# Network Monitor

Enterprise network monitoring application with automated remediation for Cisco devices.

## Features

- Real-time device monitoring (routers, switches, ASA firewalls)
- Multi-protocol support: SNMP, SSH, NETCONF, REST
- NetBox integration for device inventory
- Automated remediation playbooks
- Web UI dashboard
- CLI interface
- Webhook alerting

## Quick Start

```bash
# Start the stack
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Create admin user
docker-compose exec api python scripts/init_db.py
```

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8080 | admin/admin |
| API Docs | http://localhost:8080/docs | - |
| NetBox | http://localhost:8000 | admin/admin |

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/
```
