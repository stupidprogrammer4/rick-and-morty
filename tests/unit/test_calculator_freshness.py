from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.calculator.app.calculators import CalculatorService
from src.modules.pricing.calculator.domain.context import (
    AssetContext,
    SwitchOrderContext,
)
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.engine.domain.models import PricedSourceModel
from src.modules.pricing.sources.domain.enums import SourceSwitch
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode
from src.shared.dates import utc_now


def price(when):
    return AssetPriceModel(
        asset_id=3,
        price=2_685_000,
        buy_price=2_685_000,
        sell_price=2_685_000,
        buy_spread=0,
        sell_spread=0,
        buy_spread_rate=0,
        sell_spread_rate=0,
        priced_at=when,
    )


def calculator():
    policy = MarketEnginePolicy(
        source_timeout=10,
        asset_interval=60,
        usd_interval=30,
        aggregation="median",
        asset_scheduler_on=True,
        usd_scheduler_on=True,
        bubble_scheduler_on=True,
        outlier_rate=0.1,
        min_outlier_sample=3,
        max_quote_age_seconds=900,
    )
    return CalculatorService(*(SimpleNamespace() for _ in range(9)), policy)


def quote(source, currency, amount, stamp):
    return PricedSourceModel(
        source_id=source,
        symbol_id=1,
        currency=currency,
        price=amount,
        buy_price=amount,
        sell_price=amount,
        buy_spread=0,
        sell_spread=0,
        buy_spread_rate=0,
        sell_spread_rate=0,
        priced_at=stamp,
        is_closed=False,
        is_selected=False,
        fee=None,
    )


@pytest.mark.parametrize(
    "age,usable", [(30, True), (901, False), (14 * 3600, False), (-60, False)]
)
def test_cash_dollar_age_is_checked_before_converting_gold(age, usable):
    app = calculator()
    dollar = price(utc_now() - timedelta(seconds=age))
    assert bool(app._usd_price(dollar)) is usable


def test_stale_cash_dollar_falls_back_to_domestic_gold_without_restamping():
    app = calculator()
    now = utc_now()
    old = price(now - timedelta(hours=14))
    asset = AssetContext(
        code=AssetCode.GOLD18, asset_id=1, agg_type=AggregationType.MEDIAN
    )
    order = [
        SwitchOrderContext(code=asset.code, asset_id=1, switch=s, order=i)
        for i, s in enumerate(
            [SourceSwitch.GLOBAL_MARKET, SourceSwitch.IRAN_MARKET]
        )
    ]
    local = quote(5, CurrencyType.RIAL, 257_000_000, now)
    world = quote(17, CurrencyType.USD, 399690, now)
    result = app._priced(
        asset,
        order,
        {
            SourceSwitch.GLOBAL_MARKET: [world],
            SourceSwitch.IRAN_MARKET: [local],
        },
        None,
        app._usd_price(old),
        [],
        old.priced_at,
    )
    assert result.price == local.price
    assert result.priced_at == local.priced_at
    fresh = price(now - timedelta(minutes=5))
    result = app._priced(
        asset,
        order,
        {SourceSwitch.GLOBAL_MARKET: [world]},
        None,
        app._usd_price(fresh),
        [],
        fresh.priced_at,
    )
    assert result.priced_at == fresh.priced_at


@pytest.mark.asyncio
@pytest.mark.parametrize("sweep", [False, True])
async def test_single_and_bulk_calculation_reject_stale_fx(sweep):
    app = calculator()
    asset = AssetContext(
        code=AssetCode.GOLD18, asset_id=1, agg_type=AggregationType.MEDIAN
    )
    now = utc_now()
    world = quote(17, CurrencyType.USD, 399690, now)
    local = quote(5, CurrencyType.RIAL, 257_000_000, now)
    symbols = [
        SimpleNamespace(id=1, symbol=SymbolCode.XAU_OUNCE, asset_id=1),
        SimpleNamespace(id=2, symbol=SymbolCode.GOLD18_GRAM, asset_id=1),
    ]
    order = [
        SwitchOrderContext(code=asset.code, asset_id=1, switch=s, order=i)
        for i, s in enumerate(
            [SourceSwitch.GLOBAL_MARKET, SourceSwitch.IRAN_MARKET]
        )
    ]
    app.assets = SimpleNamespace(
        get_asset_config=AsyncMock(return_value=asset),
        get_all_config=AsyncMock(return_value=[asset]),
    )
    app.symbols = SimpleNamespace(
        get_symbols_of_asset=AsyncMock(return_value=symbols),
        get_all=AsyncMock(return_value=symbols),
    )
    app.orders = SimpleNamespace(
        get_switch_order=AsyncMock(return_value=order),
        get_all=AsyncMock(return_value=order),
    )
    app.sources = SimpleNamespace(
        get_source_switches=AsyncMock(
            return_value=[
                (17, SourceSwitch.GLOBAL_MARKET),
                (5, SourceSwitch.IRAN_MARKET),
            ]
        )
    )
    readings = {
        SymbolCode.XAU_OUNCE: [world],
        SymbolCode.GOLD18_GRAM: [local.model_copy(update={"symbol_id": 2})],
    }
    app.readings = SimpleNamespace(
        get_many_by_symbols=AsyncMock(return_value=readings),
        get_all=AsyncMock(return_value=readings),
    )
    app.bubbles = SimpleNamespace(
        get=AsyncMock(return_value=None), get_all=AsyncMock(return_value={})
    )
    app.prices = SimpleNamespace(
        get=AsyncMock(return_value=price(now - timedelta(hours=14))),
        set=AsyncMock(),
        set_many=AsyncMock(),
    )
    app.windows = SimpleNamespace(
        update_window=AsyncMock(), update_windows=AsyncMock()
    )
    app.selection = SimpleNamespace(record=AsyncMock())
    if sweep:
        assert await app.calculate_all() == 1
        result = app.prices.set_many.call_args.args[0][AssetCode.GOLD18]
    else:
        assert await app.calculate(1) == local.price
        result = app.prices.set.call_args.args[1]
    assert result.price == local.price
