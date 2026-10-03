"""Identify durable recurring missions without inventing Telegram updates."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_content_schedules"
down_revision = "20261003_schedule_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_missions",
        sa.Column("automation_key", sa.String(100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_missions_automation_key", "tbl_missions", ["automation_key"]
    )


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration for recovery")
