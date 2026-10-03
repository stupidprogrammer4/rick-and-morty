from papilio.infra.db.repositories.backends.mysql import (
    MySQLPersistenceRepository,
)

from src.modules.pricing.ticker.domain.models import (
    BubbleTickerModel,
    PriceTickerModel,
    SourceBubbleTickerModel,
    SourcePriceTickerModel,
)
from src.modules.pricing.ticker.infra.tables import (
    BubbleTickerTable,
    PriceTickerTable,
    SourceBubbleTickerTable,
    SourcePriceTickerTable,
)


class PriceTickerRepository(MySQLPersistenceRepository[PriceTickerModel]):
    table = PriceTickerTable


class BubbleTickerRepository(MySQLPersistenceRepository[BubbleTickerModel]):
    table = BubbleTickerTable


class SourcePriceTickerRepository(
    MySQLPersistenceRepository[SourcePriceTickerModel]
):
    table = SourcePriceTickerTable


class SourceBubbleTickerRepository(
    MySQLPersistenceRepository[SourceBubbleTickerModel]
):
    table = SourceBubbleTickerTable
