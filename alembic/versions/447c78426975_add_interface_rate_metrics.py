"""add_interface_rate_metrics

Revision ID: 447c78426975
Revises: 001
Create Date: 2025-12-02 00:00:38.711631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '447c78426975'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values for interface traffic rates (uppercase to match existing pattern)
    op.execute("ALTER TYPE metrictype ADD VALUE IF NOT EXISTS 'INTERFACE_IN_RATE'")
    op.execute("ALTER TYPE metrictype ADD VALUE IF NOT EXISTS 'INTERFACE_OUT_RATE'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # This would require recreating the type and all dependent columns
    pass
