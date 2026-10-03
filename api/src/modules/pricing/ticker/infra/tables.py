from papilio.infra.db.table import BaseTable

from src.modules.pricing.ticker.domain.models import (
    BubbleTickerModel,
    PriceTickerModel,
    SourceBubbleTickerModel,
    SourcePriceTickerModel,
)


class PriceTickerTable(PriceTickerModel, BaseTable, table=True):
    pass


class SourcePriceTickerTable(SourcePriceTickerModel, BaseTable, table=True):
    pass


class BubbleTickerTable(BubbleTickerModel, BaseTable, table=True):
    pass


class SourceBubbleTickerTable(SourceBubbleTickerModel, BaseTable, table=True):
    pass
