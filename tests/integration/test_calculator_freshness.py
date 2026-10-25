from datetime import UTC, datetime, timedelta

import pytest
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import select

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.infra.cache import AssetPriceCache
from src.modules.pricing.calculator.interfaces import ICalculatorService
from src.modules.pricing.engine.domain.models import PricedSourceModel
from src.modules.pricing.engine.infra.cache import SourcePriceCache
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.sources.infra.tables import SourceTable
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode
from tests.integration.test_pricing_engine import prepare_market
from tests.unit.test_calculator_freshness import price

pytestmark = pytest.mark.integration


def test_native_calculation_uses_domestic_sources_when_cash_usd_is_old(portal):
    async def workflow():
        await prepare_market(portal)
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            async with transaction():
                source = (
                    await uow.execute(
                        select(SourceTable).where(
                            SourceTable.code == SourceCode.GOLD_API
                        )
                    )
                ).scalar_one()
                source.is_active = True
                await uow.flush()
                source_id = source.id
            prices = await scope.get(AssetPriceCache)
            await prices.set(
                AssetCode.USD, price(datetime.now(UTC) - timedelta(hours=14))
            )
            cache = await scope.get(SourcePriceCache)
            await cache.set_if_priced_at_newer(
                SymbolCode.XAU_OUNCE,
                PricedSourceModel(
                    source_id=source_id,
                    symbol_id=4,
                    currency=CurrencyType.USD,
                    buy_price=399690,
                    sell_price=399690,
                    price=399690,
                    buy_spread=0,
                    sell_spread=0,
                    buy_spread_rate=0,
                    sell_spread_rate=0,
                    priced_at=datetime.now(UTC),
                ),
                max_age_seconds=900,
            )
            app = await scope.get(ICalculatorService)
            await app.calculate_all()
            gold = await prices.get(AssetCode.GOLD18)
            assert gold.price == 101_000_000
            assert (datetime.now(UTC) - gold.priced_at).total_seconds() < 30
            assert await app.calculate(gold.asset_id) == gold.price

    portal.run(workflow())
