"""Persist downloader exit labels while preserving custom settings."""

import json

import sqlalchemy as sa
from alembic import op

revision = "20261005_media_exit"
down_revision = "20261005_media_navigation"
branch_labels = None
depends_on = None

DEFAULTS = {
    "exit_button": "✖️ بستن منو",
    "exit_text": "✅ منو بسته شد. برای بازکردن دوباره /start را بفرست.",
}


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
        original = value.get("presentation", {})
        presentation = dict(original)
        for key, default in DEFAULTS.items():
            presentation.setdefault(key, default)
        if presentation == original:
            continue
        value["presentation"] = presentation
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
