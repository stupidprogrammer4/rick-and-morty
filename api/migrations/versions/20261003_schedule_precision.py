"""Preserve microseconds when persisting immediately due delivery times."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "20261003_schedule_precision"
down_revision = "20261003_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("tbl_publications", "tbl_private_replies"):
        op.alter_column(
            table,
            "scheduled_at",
            existing_type=sa.DateTime(timezone=True),
            type_=DATETIME(fsp=6),
            existing_nullable=False,
        )


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration for recovery")
