from papilio.infra.db.schema.entity import BaseEntity, PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    EnumField,
    ForeignKeyField,
)

from src.modules.pricing.candle.domain.enums import TimeFrame


class CandleData(BaseEntity):
    timeframe: TimeFrame = EnumField(
        TimeFrame,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=8,
    )

    open: int = BigIntField()
    high: int = BigIntField()
    low: int = BigIntField()
    close: int = BigIntField()

    st_ts: int = BigIntField()
    en_ts: int = BigIntField()


class CandleModel(PersistenceEntity, CandleData):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        index=True,
    )


class SourceCandleModel(PersistenceEntity, CandleData):
    symbol_id: int = ForeignKeyField(
        "tbl_symbols.id",
        ondelete="CASCADE",
        index=True,
    )
    source_id: int = ForeignKeyField(
        "tbl_sources.id",
        ondelete="CASCADE",
        index=True,
    )


class CandleReadModel(BaseEntity):
    open: int
    high: int
    low: int
    close: int
    st_ts: int
    en_ts: int


class CandleChartModel(BaseEntity):
    timeframe: TimeFrame
    candles: list[CandleReadModel]
    from_timestamp: int
    to_timestamp: int
