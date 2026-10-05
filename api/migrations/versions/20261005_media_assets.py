"""Cache successful media deliveries without storing local files."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_media_assets"
down_revision = "20261004_media_parallel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_media_assets",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
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
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.String(512), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cache_key"),
    )
    op.create_index(
        "ix_media_assets_expires", "tbl_media_assets", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_media_assets_expires", table_name="tbl_media_assets")
    op.drop_table("tbl_media_assets")
