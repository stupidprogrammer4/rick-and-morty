from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import select
from sqlmodel import col

from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.candle.domain.models import (
    CandleChartModel,
    CandleReadModel,
)
from src.modules.pricing.candle.infra.tables import SourceCandleTable
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.infra.tables import SymbolTable


class GlobalGoldSeries(MySQLReader):
    async def read(
        self, source_id: int, start: int, end: int
    ) -> CandleChartModel:
        t = SourceCandleTable
        result = await self.uow.execute(
            select(t)
            .join(SymbolTable, col(t.symbol_id) == col(SymbolTable.id))
            .where(
                col(t.source_id) == source_id,
                col(SymbolTable.code) == SymbolCode.XAU_OUNCE,
                col(t.timeframe) == TimeFrame.FIVE_MINUTE,
                col(t.st_ts) >= start,
                col(t.en_ts) <= end,
            )
            .order_by(col(t.st_ts))
        )
        return CandleChartModel(
            timeframe=TimeFrame.FIVE_MINUTE,
            from_timestamp=start,
            to_timestamp=end,
            candles=[
                CandleReadModel.model_validate(row, from_attributes=True)
                for row in result.scalars()
            ],
        )
