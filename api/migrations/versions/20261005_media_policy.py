"""Persist native media options while preserving existing configuration."""

import json

import sqlalchemy as sa
from alembic import op

revision = "20261005_media_policy"
down_revision = "20261005_media_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    defaults = {
        "youtube_clients": ["mweb", "web_safari", "android_vr"],
        "music_sources": ["soundcloud", "youtube"],
        "music_search_results": 5,
        "music_match_threshold": 0.8,
        "music_duration_tolerance": 0.08,
        "file_cache_seconds": 604800,
        "hls_max_segments": 512,
        "hls_segment_concurrency": 2,
        "spotify_auth_url": "https://accounts.spotify.com/api/token",
        "spotify_api_url": "https://api.spotify.com/v1",
    }
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT v.id, v.value FROM tbl_setting_values v "
            "JOIN tbl_setting_definitions d ON d.id = v.definition_id "
            "WHERE d.`key` = 'media.policy'"
        )
    ).all()
    for id, value in rows:
        saved = json.loads(value)
        if all(key in saved for key in defaults):
            continue
        saved = defaults | saved
        connection.execute(
            sa.text(
                "UPDATE tbl_setting_values SET value = :value, "
                "revision = revision + 1, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = :id"
            ),
            {"id": id, "value": json.dumps(saved, ensure_ascii=False)},
        )


def downgrade() -> None:
    # Retain user configuration when rolling back the application.
    pass
