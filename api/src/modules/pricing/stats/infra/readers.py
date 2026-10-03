from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import JSON, func, select
from sqlmodel import col

from src.modules.pricing.assets.infra.tables import (
    AssetConfigTable,
    AssetTable,
)
from src.modules.pricing.sources.infra.tables import SourceTable
from src.modules.pricing.stats.domain.models import (
    PricingCounts,
    PricingStatisticsCriteria,
)
from src.modules.pricing.symbols.infra.tables import SymbolTable


class PricingStatisticsReader(MySQLReader):
    async def counts(
        self, criteria: PricingStatisticsCriteria
    ) -> PricingCounts:
        result = await self.uow.execute(
            select(
                select(func.count())
                .select_from(SourceTable)
                .scalar_subquery()
                .label("sources"),
                select(func.count())
                .select_from(SourceTable)
                .where(col(SourceTable.is_active).is_(criteria.active))
                .scalar_subquery()
                .label("active_sources"),
                select(func.count())
                .select_from(SourceTable)
                .where(
                    col(SourceTable.error).is_not(None),
                    col(SourceTable.error) != JSON.NULL,
                )
                .scalar_subquery()
                .label("failed_sources"),
                select(func.count())
                .select_from(AssetTable)
                .scalar_subquery()
                .label("assets"),
                select(func.count())
                .select_from(AssetConfigTable)
                .where(
                    col(AssetConfigTable.scheduler_on).is_(
                        criteria.scheduler_off
                    )
                )
                .scalar_subquery()
                .label("scheduler_off_assets"),
                select(func.count())
                .select_from(SymbolTable)
                .scalar_subquery()
                .label("symbols"),
            )
        )
        return PricingCounts.model_validate(result.mappings().one())
