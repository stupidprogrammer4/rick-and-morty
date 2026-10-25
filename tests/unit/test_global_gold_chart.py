import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from portal_contracts.charts import AssetChartPolicy
from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.candle.domain.models import (
    CandleChartModel,
    CandleReadModel,
)
from src.modules.pricing.charts.app.global_gold import GlobalGoldChartQuery
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.domain.models import (
    GlobalGoldChartCard,
    GlobalGoldInstrument,
)
from src.modules.pricing.charts.infra.browser import ChartAssets
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode


def history():
    return CandleChartModel(
        timeframe=TimeFrame.FIVE_MINUTE,
        from_timestamp=0,
        to_timestamp=300,
        candles=[
            CandleReadModel(
                st_ts=0,
                en_ts=300,
                open=402760,
                high=402810,
                low=402700,
                close=402775,
            )
        ],
    )


def test_global_gold_renders_usd_cents_consistently_in_ohlc_and_line():
    card = GlobalGoldChartCard(
        instrument=GlobalGoldInstrument(source_id=17),
        chart=history(),
        style=AssetChartPolicy(
            candle_interval_seconds=300, unit_label="USD / troy oz"
        ),
        timezone="UTC",
        caption="Gold",
    )
    doc = AssetChartRenderer(SimpleNamespace(), ChartAssets()).document(card)
    data = json.loads(
        doc.html.split('<script type="application/json" id="chart-data">')[
            1
        ].split("</script>")[0]
    )
    assert data["candles"][0]["open"] == 4027.60
    assert data["line"][0]["y"] == 4027.75
    assert data["latest"] == 4027.75
    assert data["decimals"] == 2
    assert "4,027.75" in doc.html and "USD / troy oz" in doc.html


@pytest.mark.asyncio
async def test_global_gold_uses_fresh_raw_usd_source_without_cash_usd(
    snapshot,
):
    quote = SimpleNamespace(
        source_id=17,
        currency=CurrencyType.USD,
        price=402760,
        is_closed=False,
        is_selected=False,
        priced_at=datetime.now(UTC),
    )
    reader = SimpleNamespace(
        get_many_by_symbols=AsyncMock(
            return_value={SymbolCode.XAU_OUNCE: [quote]}
        )
    )
    sources = SimpleNamespace(
        get_all=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=17,
                    is_active=True,
                    title="Gold",
                    website_url="https://gold.example/",
                )
            ]
        )
    )
    series = SimpleNamespace(read=AsyncMock(return_value=history()))
    query = GlobalGoldChartQuery(reader, sources, series, snapshot[0])
    card = await query.get()
    assert card is not None and card.quote.price == 402760
    assert card.instrument.source_id == 17 and card.price_divisor == 100
    start, end = series.read.await_args.args[1:]
    assert end - start == 43200
    quote.priced_at -= timedelta(days=1)
    assert await query.get() is None
    series.read.assert_awaited_once()


@pytest.mark.asyncio
async def test_unchanged_global_gold_is_explained_in_chart(snapshot):
    now = datetime.now(UTC)
    reader = SimpleNamespace(
        get_many_by_symbols=AsyncMock(
            return_value={
                SymbolCode.XAU_OUNCE: [
                    SimpleNamespace(
                        source_id=17,
                        currency=CurrencyType.USD,
                        price=399690,
                        is_closed=False,
                        priced_at=now,
                    )
                ]
            }
        )
    )
    sources = SimpleNamespace(
        get_all=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=17,
                    is_active=True,
                    title="Gold",
                    website_url="https://gold.example/",
                )
            ]
        )
    )
    chart = history()
    chart.candles = [
        CandleReadModel(
            st_ts=i * 300,
            en_ts=(i + 1) * 300,
            open=399690,
            high=399690,
            low=399690,
            close=399690,
        )
        for i in range(3)
    ]
    card = await GlobalGoldChartQuery(
        reader,
        sources,
        SimpleNamespace(read=AsyncMock(return_value=chart)),
        snapshot[0],
    ).get()
    assert "بدون تغییر" in card.caption
    assert "بدون تغییر" in card.style.footer
    assert card.style.recorded_label == "آخرین دریافت از منبع"
