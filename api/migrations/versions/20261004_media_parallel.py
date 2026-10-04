"""Track independent playlist item leases and retry times."""

import sqlalchemy as sa
from alembic import op

revision = "20261004_media_parallel"
down_revision = "20261004_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_media_items",
        sa.Column("downloaded_payload", sa.Text(), nullable=True),
    )
    op.add_column(
        "tbl_media_items",
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tbl_media_items",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_media_items_lease",
        "tbl_media_items",
        ["status", "lease_until"],
        unique=False,
    )
    op.execute(
        sa.text(
            "UPDATE tbl_media_items i JOIN tbl_media_jobs j "
            "ON j.id = i.job_id "
            "SET i.lease_until = COALESCE(j.lease_until, CURRENT_TIMESTAMP) "
            "WHERE i.status IN ('downloading', 'sending')"
        )
    )


def downgrade() -> None:
    active = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM tbl_media_items "
                "WHERE status IN "
                "('reserved', 'downloading', 'ready', 'sending')"
            )
        )
        .scalar_one()
    )
    if active:
        raise RuntimeError("Active media transfers prevent lease removal")
    op.drop_index("ix_media_items_lease", table_name="tbl_media_items")
    op.drop_column("tbl_media_items", "available_at")
    op.drop_column("tbl_media_items", "lease_until")
    op.drop_column("tbl_media_items", "downloaded_payload")
