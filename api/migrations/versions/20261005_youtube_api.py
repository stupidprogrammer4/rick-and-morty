"""Persist the optional YouTube source endpoint without replacing settings."""

import json

import sqlalchemy as sa
from alembic import op

revision = "20261005_youtube_api"
down_revision = "20261005_media_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT v.id, v.value FROM tbl_setting_values v "
            "JOIN tbl_setting_definitions d ON d.id = v.definition_id "
            "WHERE d.`key` = 'media.policy'"
        )
    ).all()
    for id, raw in rows:
        value = json.loads(raw)
        if "youtube_api_url" in value:
            continue
        value["youtube_api_url"] = None
        connection.execute(
            sa.text(
                "UPDATE tbl_setting_values SET value=:value, "
                "revision=revision+1, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=:id"
            ),
            {"id": id, "value": json.dumps(value, ensure_ascii=False)},
        )


def downgrade() -> None:
    pass
