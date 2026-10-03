"""Add paginated publications and asset chart deliveries"""

import sqlalchemy as sa
from alembic import op

revision = "20261003_publication_charts"
down_revision = "20261003_market_engine"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tbl_publication_charts",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("publication_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["tbl_assets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["tbl_publications.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_id", "asset_id"),
    )
    op.create_index(
        "ix_publication_charts_due",
        "tbl_publication_charts",
        ["status", "scheduled_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_publication_charts_publication_id"),
        "tbl_publication_charts",
        ["publication_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_publication_charts_status"),
        "tbl_publication_charts",
        ["status"],
        unique=False,
    )
    op.add_column(
        "tbl_publications", sa.Column("pages", sa.Text(), nullable=True)
    )


def downgrade():
    connection = op.get_bind()
    charts = connection.execute(
        sa.text("SELECT COUNT(*) FROM tbl_publication_charts")
    ).scalar_one()
    pages = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM tbl_publications WHERE pages IS NOT NULL"
        )
    ).scalar_one()
    if charts or pages:
        raise RuntimeError(
            "Recorded pages or charts prevent a destructive downgrade"
        )
    op.drop_column("tbl_publications", "pages")
    op.drop_index(
        op.f("ix_tbl_publication_charts_status"),
        table_name="tbl_publication_charts",
    )
    op.drop_index(
        op.f("ix_tbl_publication_charts_publication_id"),
        table_name="tbl_publication_charts",
    )
    op.drop_index(
        "ix_publication_charts_due", table_name="tbl_publication_charts"
    )
    op.drop_table("tbl_publication_charts")
