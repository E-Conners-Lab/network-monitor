# Network Monitoring Application - Implementation Plan

## Overview
A Dockerized Python application for monitoring ~20 Cisco devices (routers, switches, ASA firewalls) with real-time monitoring, automated remediation, NetBox integration, and a web GUI + CLI.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                         │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   FastAPI   │  │   Celery    │  │   Redis     │  │ PostgreSQL │ │
│  │  (Web API)  │  │  (Workers)  │  │  (Broker)   │  │    (DB)    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Core Monitoring Engine                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │   │
│  │  │  SNMP   │  │   SSH   │  │  REST   │  │ NETCONF/YANG    │ │   │
│  │  │ Poller  │  │ Client  │  │ Client  │  │    Client       │ │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    NetBox Integration                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | FastAPI | Async API + WebSocket support |
| Task Queue | Celery + Redis | Background monitoring & remediation |
| Database | PostgreSQL | Historical data, alerts, configs |
| Cache/Broker | Redis | Real-time pub/sub, task queue |
| Web UI | React + TailwindCSS | Dashboard |
| CLI | Typer | Command-line interface |
| Network Libraries | Netmiko, NAPALM, PySNMP, ncclient | Device interaction |
| NetBox | pynetbox | Inventory integration |
| Containerization | Docker Compose | Deployment |

## Project Structure

```
network-monitor/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── devices.py
│   │   ├── alerts.py
│   │   ├── metrics.py
│   │   └── websocket.py
│   ├── cli/
│   │   └── commands.py
│   ├── core/
│   │   ├── monitor.py
│   │   ├── health_checks.py
│   │   └── event_bus.py
│   ├── drivers/
│   │   ├── base.py
│   │   ├── snmp_driver.py
│   │   ├── ssh_driver.py
│   │   ├── netconf_driver.py
│   │   └── rest_driver.py
│   ├── integrations/
│   │   └── netbox.py
│   ├── remediation/
│   │   ├── engine.py
│   │   ├── playbooks/
│   │   └── rules.py
│   ├── models/
│   │   ├── device.py
│   │   ├── metric.py
│   │   ├── alert.py
│   │   └── remediation_log.py
│   ├── schemas/
│   └── tasks/
│       ├── polling.py
│       └── remediation.py
├── frontend/
│   ├── package.json
│   └── src/
├── tests/
└── scripts/
```

## Implementation Phases

### Phase 1: Foundation
- [ ] Project scaffolding with Docker Compose
- [ ] Database models and migrations (SQLAlchemy + Alembic)
- [ ] Basic FastAPI skeleton with health endpoint
- [ ] Configuration management (pydantic-settings)

### Phase 2: Device Connectivity
- [ ] Protocol drivers (SNMP, SSH/Netmiko, NETCONF)
- [ ] NetBox integration
- [ ] Device CRUD API

### Phase 3: Monitoring Engine
- [ ] Celery-based polling tasks
- [ ] Metric collection and storage
- [ ] Real-time WebSocket streaming

### Phase 4: Alerting & Remediation
- [ ] Alert rules engine
- [ ] Remediation playbooks for common issues
- [ ] Execution logging and audit trail

### Phase 5: Web UI
- [ ] Dashboard with device overview
- [ ] Real-time metrics charts
- [ ] Alert management interface

### Phase 6: CLI
- [ ] Device management commands
- [ ] Manual remediation triggers
- [ ] Status queries

## Automated Remediation Playbooks

| Issue | Detection | Remediation |
|-------|-----------|-------------|
| Interface down | SNMP trap / polling | `no shutdown` via SSH |
| High CPU | SNMP threshold (>80%) | Clear processes, alert if persistent |
| BGP neighbor down | SNMP/NETCONF | Clear BGP session, verify config |
| Memory critical | SNMP threshold (>90%) | Clear caches, identify memory hogs |
| ASA failover | SNMP/REST | Log event, verify standby health |

## Pending Decisions

- [ ] NetBox: Include in Docker stack or external?
- [ ] Notification channels: Email, Slack, Teams, PagerDuty?
- [ ] Authentication: Required for web UI?
- [ ] Credential storage: NetBox secrets, env vars, Vault, or encrypted config?
