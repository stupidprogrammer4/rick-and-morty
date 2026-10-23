"""One durable chart gallery per publication, preserving legacy receipts."""

import sqlalchemy as sa
from alembic import op

revision = "20261023_chart_gallery"
down_revision = "20261013_groq_model"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "tbl_publication_charts",
        "asset_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.add_column(
        "tbl_publication_charts",
        sa.Column("gallery_key", sa.String(16), nullable=True),
    )
    op.create_unique_constraint(
        "uq_chart_gallery",
        "tbl_publication_charts",
        ["publication_id", "gallery_key"],
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM tbl_publication_charts "
                "WHERE asset_id IS NULL"
            )
        )
        .scalar()
    ):
        raise RuntimeError(
            "Gallery receipts exist; restore a pre-gallery backup to downgrade"
        )
    op.drop_constraint(
        "uq_chart_gallery", "tbl_publication_charts", type_="unique"
    )
    op.drop_column("tbl_publication_charts", "gallery_key")
    op.alter_column(
        "tbl_publication_charts",
        "asset_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
