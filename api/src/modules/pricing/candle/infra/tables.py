from papilio.infra.db.table import BaseTable
from sqlmodel import UniqueConstraint

from src.modules.pricing.candle.domain.models import (
    CandleModel,
    SourceCandleModel,
)


class CandleTable(CandleModel, BaseTable, table=True):
    __table_args__ = (UniqueConstraint("asset_id", "timeframe", "st_ts"),)


class SourceCandleTable(SourceCandleModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("symbol_id", "source_id", "timeframe", "st_ts"),
    )
