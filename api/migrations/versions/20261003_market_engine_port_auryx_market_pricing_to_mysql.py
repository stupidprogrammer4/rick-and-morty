"""Port Auryx market pricing to MySQL"""

import sqlalchemy as sa
from alembic import op

revision = "20261003_market_engine"
down_revision = "20261003_content_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_assets",
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
        sa.Column("title", sa.String(length=55), nullable=False),
        sa.Column(
            "code",
            sa.Enum(
                "gold18",
                "silver999",
                "usd",
                name="assetcode",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=55), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "tbl_bubbles",
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
        sa.Column(
            "code",
            sa.Enum(
                "gold18",
                "silver999",
                "usd",
                name="assetcode",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=55), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "tbl_sources",
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
        sa.Column("title", sa.String(length=55), nullable=False),
        sa.Column(
            "code",
            sa.Enum(
                "digikala",
                "goldika",
                "meligold",
                "miligold",
                "hanzaei",
                "mirrokni",
                "noghresea",
                "talaland",
                "talasea",
                "taline",
                "technogold",
                "wallgold",
                "alanchand",
                "estjt",
                "tgju",
                "wallex",
                "gold_api",
                "goldprice_dev",
                name="sourcecode",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column("website_url", sa.String(length=255), nullable=False),
        sa.Column("icon_url", sa.String(length=255), nullable=False),
        sa.Column("primary_color", sa.String(length=16), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "supplier",
                "global_market",
                "iran_market",
                name="sourceswitch",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column(
            "update_type",
            sa.Enum(
                "scheduler",
                "event",
                name="sourceupdatetype",
                native_enum=False,
                length=35,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "error",
            sa.JSON(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "tbl_asset_configs",
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
        sa.Column("scheduler_on", sa.Boolean(), nullable=False),
        sa.Column("scheduler_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "agg_type",
            sa.Enum(
                "median",
                "mean",
                "min",
                "max",
                "first_quartile",
                "third_quartile",
                name="aggregationtype",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        op.f("ix_tbl_asset_configs_asset_id"),
        "tbl_asset_configs",
        ["asset_id"],
        unique=False,
    )
    op.create_table(
        "tbl_asset_switches",
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
        sa.Column(
            "switch",
            sa.Enum(
                "supplier",
                "global_market",
                "iran_market",
                name="sourceswitch",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "switch"),
    )
    op.create_index(
        op.f("ix_tbl_asset_switches_asset_id"),
        "tbl_asset_switches",
        ["asset_id"],
        unique=False,
    )
    op.create_table(
        "tbl_bubble_configs",
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
        sa.Column("scheduler_on", sa.Boolean(), nullable=False),
        sa.Column("scheduler_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "agg_type",
            sa.Enum(
                "median",
                "mean",
                "min",
                "max",
                "first_quartile",
                "third_quartile",
                name="aggregationtype",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column("bubble_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bubble_id"], ["tbl_bubbles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("bubble_id"),
    )
    op.create_index(
        op.f("ix_tbl_bubble_configs_bubble_id"),
        "tbl_bubble_configs",
        ["bubble_id"],
        unique=False,
    )
    op.create_table(
        "tbl_bubble_tickers",
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
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_bubble_tickers_asset_id"),
        "tbl_bubble_tickers",
        ["asset_id"],
        unique=False,
    )
    op.create_table(
        "tbl_candles",
        sa.Column(
            "timeframe",
            sa.Enum(
                "5m",
                "1h",
                "5h",
                "1d",
                name="timeframe",
                native_enum=False,
                length=8,
            ),
            nullable=False,
        ),
        sa.Column("open", sa.BigInteger(), nullable=False),
        sa.Column("high", sa.BigInteger(), nullable=False),
        sa.Column("low", sa.BigInteger(), nullable=False),
        sa.Column("close", sa.BigInteger(), nullable=False),
        sa.Column("st_ts", sa.BigInteger(), nullable=False),
        sa.Column("en_ts", sa.BigInteger(), nullable=False),
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
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "timeframe", "st_ts"),
    )
    op.create_index(
        op.f("ix_tbl_candles_asset_id"),
        "tbl_candles",
        ["asset_id"],
        unique=False,
    )
    op.create_table(
        "tbl_price_tickers",
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
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_price_tickers_asset_id"),
        "tbl_price_tickers",
        ["asset_id"],
        unique=False,
    )
    op.create_table(
        "tbl_source_bubble_tickers",
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
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tbl_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_source_bubble_tickers_asset_id"),
        "tbl_source_bubble_tickers",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_source_bubble_tickers_source_id"),
        "tbl_source_bubble_tickers",
        ["source_id"],
        unique=False,
    )
    op.create_table(
        "tbl_source_configs",
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
        sa.Column("timeout", sa.Integer(), nullable=False),
        sa.Column(
            "fetchers",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "login",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "headers_credentials",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "auth_credentials",
            sa.JSON(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tbl_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        op.f("ix_tbl_source_configs_source_id"),
        "tbl_source_configs",
        ["source_id"],
        unique=False,
    )
    op.create_table(
        "tbl_symbols",
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
        sa.Column("title", sa.String(length=55), nullable=False),
        sa.Column(
            "code",
            sa.Enum(
                "gold18_gram",
                "gold18_mazane",
                "xau_ounce",
                "silver_gram",
                "xag_ounce",
                "usd_rial",
                name="symbolcode",
                native_enum=False,
                length=55,
            ),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.Enum(
                "rial",
                "usd",
                name="currencytype",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=55), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["tbl_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        op.f("ix_tbl_symbols_asset_id"),
        "tbl_symbols",
        ["asset_id"],
        unique=False,
    )
    op.create_table(
        "tbl_source_candles",
        sa.Column(
            "timeframe",
            sa.Enum(
                "5m",
                "1h",
                "5h",
                "1d",
                name="timeframe",
                native_enum=False,
                length=8,
            ),
            nullable=False,
        ),
        sa.Column("open", sa.BigInteger(), nullable=False),
        sa.Column("high", sa.BigInteger(), nullable=False),
        sa.Column("low", sa.BigInteger(), nullable=False),
        sa.Column("close", sa.BigInteger(), nullable=False),
        sa.Column("st_ts", sa.BigInteger(), nullable=False),
        sa.Column("en_ts", sa.BigInteger(), nullable=False),
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
        sa.Column("symbol_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tbl_sources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["symbol_id"], ["tbl_symbols.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol_id", "source_id", "timeframe", "st_ts"),
    )
    op.create_index(
        op.f("ix_tbl_source_candles_source_id"),
        "tbl_source_candles",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_source_candles_symbol_id"),
        "tbl_source_candles",
        ["symbol_id"],
        unique=False,
    )
    op.create_table(
        "tbl_source_price_tickers",
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
        sa.Column("symbol_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["tbl_sources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["symbol_id"], ["tbl_symbols.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_source_price_tickers_source_id"),
        "tbl_source_price_tickers",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_source_price_tickers_symbol_id"),
        "tbl_source_price_tickers",
        ["symbol_id"],
        unique=False,
    )


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration for recovery")
