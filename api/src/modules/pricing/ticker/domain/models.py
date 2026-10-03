from papilio.infra.db.schema.entity import BaseEntity, PersistenceEntity
from papilio.infra.db.schema.fields import BigIntField, ForeignKeyField

from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.ticker.domain.enums import ChartType


class PriceTickerModel(PersistenceEntity):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        index=True,
    )
    price: int = BigIntField()
    timestamp: int = BigIntField()


class SourcePriceTickerModel(PersistenceEntity):
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

    price: int = BigIntField()
    timestamp: int = BigIntField()


class BubbleTickerModel(PersistenceEntity):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        index=True,
    )
    price: int = BigIntField()
    timestamp: int = BigIntField()


class SourceBubbleTickerModel(PersistenceEntity):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        index=True,
    )
    source_id: int = ForeignKeyField(
        "tbl_sources.id",
        ondelete="CASCADE",
        index=True,
    )

    price: int = BigIntField()
    timestamp: int = BigIntField()


class PointOutputModel(BaseEntity):
    price: int
    timestamp: int


class AssetPointReadModel(PointOutputModel):
    asset_id: int


class SourcePricePointReadModel(PointOutputModel):
    source_id: int
    symbol_id: int


class SourceBubblePointReadModel(AssetPointReadModel):
    source_id: int


class BaseChartOutputModel(BaseEntity):
    type: ChartType
    points: list[PointOutputModel]
    from_timestamp: int
    to_timestamp: int


class SourceChartOutputModel(BaseChartOutputModel):
    source_points: dict[SourceCode, list[PointOutputModel]]


class ChartOutputModel(BaseChartOutputModel):
    points: list[PointOutputModel]
    max: int
    min: int
    mean: int
    change_rate: float
