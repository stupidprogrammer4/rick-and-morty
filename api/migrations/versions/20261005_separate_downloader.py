"""Retire downloader persistence while preserving its historical data."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_separate_downloader"
down_revision = "20261005_media_exit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    active = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM tbl_media_jobs "
                "WHERE status IN ('queued', 'planning', 'running')"
            )
        )
        .scalar_one()
    )
    if active:
        raise RuntimeError(
            "Finish or transfer active downloads before retirement"
        )
    op.execute(
        sa.text(
            "CREATE TABLE archive_downloader_definitions "
            "LIKE tbl_setting_definitions"
        )
    )
    op.execute(
        sa.text(
            "CREATE TABLE archive_downloader_values LIKE tbl_setting_values"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO archive_downloader_definitions "
            "SELECT * FROM tbl_setting_definitions WHERE `key`='media.policy'"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO archive_downloader_values SELECT v.* "
            "FROM tbl_setting_values v JOIN tbl_setting_definitions d "
            "ON d.id=v.definition_id WHERE d.`key`='media.policy'"
        )
    )
    op.execute(
        sa.text(
            "DELETE v FROM tbl_setting_values v "
            "JOIN tbl_setting_definitions d ON d.id=v.definition_id "
            "WHERE d.`key`='media.policy'"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM tbl_setting_definitions WHERE `key`='media.policy'"
        )
    )
    op.execute(
        sa.text(
            "RENAME TABLE tbl_media_jobs TO archive_downloader_jobs, "
            "tbl_media_items TO archive_downloader_items, "
            "tbl_media_assets TO archive_downloader_assets"
        )
    )


def downgrade() -> None:
    raise RuntimeError("Restore the archived downloader data before rollback")
