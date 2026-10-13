"""Move live OpenRouter policies to the approved Groq Free Plan."""

import sqlalchemy as sa
from alembic import op

revision = "20261013_groq_model"
down_revision = "20261011_occasion_catalogue"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE tbl_setting_values AS v "
            "JOIN tbl_setting_definitions AS d ON d.id = v.definition_id "
            "SET v.value = JSON_SET(v.value, '$.mode', 'groq', "
            "'$.model', 'qwen/qwen3.8-27b', '$.reasoning_effort', NULL, "
            "'$.input_usd_per_million', '0', '$.output_usd_per_million', '0', "
            "'$.maximum_request_usd', '0'), v.revision = v.revision + 1 "
            "WHERE d.`key` = 'ai.model' "
            "AND JSON_UNQUOTE(JSON_EXTRACT(v.value, '$.mode')) = 'openrouter'"
        )
    )


def downgrade():
    raise RuntimeError("Restore the AI policy from a pre-migration backup")
