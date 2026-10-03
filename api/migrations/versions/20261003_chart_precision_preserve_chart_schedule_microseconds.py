"""Preserve chart schedule microseconds."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261003_chart_precision"
down_revision = "20261003_publication_charts"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "tbl_publication_charts",
        "scheduled_at",
        existing_type=mysql.DATETIME(),
        type_=mysql.DATETIME(fsp=6),
        existing_nullable=False,
    )


def downgrade():
    connection = op.get_bind()
    recorded = connection.execute(
        sa.text(
            "SELECT (SELECT COUNT(*) FROM tbl_publication_charts) + "
            "(SELECT COUNT(*) FROM tbl_publications WHERE pages IS NOT NULL)"
        )
    ).scalar_one()
    if recorded:
        raise RuntimeError(
            "Recorded pages or charts prevent a destructive downgrade"
        )
    op.alter_column(
        "tbl_publication_charts",
        "scheduled_at",
        existing_type=mysql.DATETIME(fsp=6),
        type_=mysql.DATETIME(),
        existing_nullable=False,
    )
