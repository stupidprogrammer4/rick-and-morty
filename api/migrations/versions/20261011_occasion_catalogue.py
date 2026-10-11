"""Add source-backed editable occasions."""

import json
from importlib.resources import files

import sqlalchemy as sa
from alembic import op

revision = "20261011_occasion_catalogue"
down_revision = "20261006_restore_news_style"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "tbl_occasions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    entries = json.loads(
        files("amupouya_calendar")
        .joinpath("data", "catalogue_20261011.json")
        .read_text()
    )
    op.bulk_insert(
        table,
        [
            dict(
                key=e["id"],
                definition=json.dumps(e, ensure_ascii=False),
                enabled=True,
                revision=1,
            )
            for e in entries
        ],
    )


def downgrade() -> None:
    op.drop_table("tbl_occasions")
