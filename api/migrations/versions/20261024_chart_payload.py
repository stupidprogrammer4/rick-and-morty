"""Keep full twelve-hour galleries without the TEXT byte ceiling."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261024_chart_payload"
down_revision = "20261023_chart_gallery"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "tbl_publication_charts",
        "payload",
        existing_type=sa.Text(),
        type_=mysql.MEDIUMTEXT(),
        nullable=False,
    )


def downgrade():
    oversized = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM tbl_publication_charts "
                "WHERE OCTET_LENGTH(payload) > 65535"
            )
        )
        .scalar_one()
    )
    if oversized:
        raise RuntimeError(
            "Full galleries exceed TEXT; preserve their receipts"
        )
    op.alter_column(
        "tbl_publication_charts",
        "payload",
        existing_type=mysql.MEDIUMTEXT(),
        type_=sa.Text(),
        nullable=False,
    )
