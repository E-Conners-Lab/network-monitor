"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # Devices table
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column(
            "device_type",
            sa.Enum("ROUTER", "SWITCH", "FIREWALL", "ACCESS_POINT", "OTHER", name="devicetype"),
            nullable=False,
        ),
        sa.Column("vendor", sa.String(length=50), nullable=False, default="cisco"),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("os_version", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_reachable", sa.Boolean(), nullable=False, default=False),
        sa.Column("last_seen", sa.String(length=50), nullable=True),
        sa.Column("snmp_community", sa.String(length=100), nullable=True),
        sa.Column("snmp_version", sa.Integer(), nullable=False, default=2),
        sa.Column("ssh_port", sa.Integer(), nullable=False, default=22),
        sa.Column("netconf_port", sa.Integer(), nullable=False, default=830),
        sa.Column("netbox_id", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        sa.UniqueConstraint("name", name="uq_devices_name"),
    )
    op.create_index("ix_devices_name", "devices", ["name"])
    op.create_index("ix_devices_ip_address", "devices", ["ip_address"])
    op.create_index("ix_devices_netbox_id", "devices", ["netbox_id"])

    # Metrics table
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column(
            "metric_type",
            sa.Enum(
                "CPU_UTILIZATION",
                "MEMORY_UTILIZATION",
                "UPTIME",
                "INTERFACE_STATUS",
                "INTERFACE_IN_OCTETS",
                "INTERFACE_OUT_OCTETS",
                "INTERFACE_IN_ERRORS",
                "INTERFACE_OUT_ERRORS",
                "BGP_NEIGHBOR_STATE",
                "OSPF_NEIGHBOR_STATE",
                "CONNECTION_COUNT",
                "FAILOVER_STATUS",
                "PING_LATENCY",
                "PING_LOSS",
                "CUSTOM",
                name="metrictype",
            ),
            nullable=False,
        ),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("context", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name="fk_metrics_device_id_devices"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_metrics"),
    )
    op.create_index("ix_metrics_device_id", "metrics", ["device_id"])
    op.create_index(
        "ix_metrics_device_type_created", "metrics", ["device_id", "metric_type", "created_at"]
    )

    # Alerts table
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("INFO", "WARNING", "CRITICAL", name="alertseverity"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "ACKNOWLEDGED", "RESOLVED", name="alertstatus"),
            nullable=False,
            default="ACTIVE",
        ),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("webhook_sent", sa.Boolean(), nullable=False, default=False),
        sa.Column("webhook_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name="fk_alerts_device_id_devices"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_alerts"),
    )
    op.create_index("ix_alerts_device_id", "alerts", ["device_id"])

    # Remediation logs table
    op.create_table(
        "remediation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("playbook_name", sa.String(length=100), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "IN_PROGRESS", "SUCCESS", "FAILED", "SKIPPED", name="remediationstatus"
            ),
            nullable=False,
            default="PENDING",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("state_before", sa.JSON(), nullable=True),
        sa.Column("state_after", sa.JSON(), nullable=True),
        sa.Column("commands_executed", sa.JSON(), nullable=True),
        sa.Column("command_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, default=1),
        sa.Column("max_attempts", sa.Integer(), nullable=False, default=3),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name="fk_remediation_logs_device_id_devices"
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["alerts.id"], name="fk_remediation_logs_alert_id_alerts"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_remediation_logs"),
    )
    op.create_index("ix_remediation_logs_device_id", "remediation_logs", ["device_id"])
    op.create_index("ix_remediation_logs_alert_id", "remediation_logs", ["alert_id"])


def downgrade() -> None:
    op.drop_table("remediation_logs")
    op.drop_table("alerts")
    op.drop_table("metrics")
    op.drop_table("devices")
    op.drop_table("users")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS remediationstatus")
    op.execute("DROP TYPE IF EXISTS alertstatus")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS metrictype")
    op.execute("DROP TYPE IF EXISTS devicetype")
