"""Add public media jobs and playlist items."""

import sqlalchemy as sa
from alembic import op

revision = "20261004_media"
down_revision = "20261003_chart_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_media_jobs",
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
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("sent", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "update_id"),
    )
    op.create_index(
        "ix_media_jobs_due", "tbl_media_jobs", ["status", "id"], unique=False
    )
    op.create_index(
        "ix_media_jobs_owner_status",
        "tbl_media_jobs",
        ["owner_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_media_jobs_owner_id"),
        "tbl_media_jobs",
        ["owner_id"],
        unique=False,
    )
    op.create_table(
        "tbl_media_items",
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
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("filename", sa.String(length=100), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("file_id", sa.String(length=512), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"], ["tbl_media_jobs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "position"),
    )
    op.create_index(
        "ix_media_items_due",
        "tbl_media_items",
        ["job_id", "status", "position"],
        unique=False,
    )


def downgrade() -> None:
    count = (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM tbl_media_jobs"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "Recorded media requests prevent a destructive downgrade"
        )
    op.drop_table("tbl_media_items")
    op.drop_table("tbl_media_jobs")
