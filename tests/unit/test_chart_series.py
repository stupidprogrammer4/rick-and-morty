from portal_contracts.charts import AssetChartPolicy
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.candle.domain.models import (
    CandleChartModel,
    CandleReadModel,
)
from src.modules.pricing.charts.app.series import ChartSeries
from src.modules.pricing.charts.domain.models import AssetChartCard, ChartAsset


def test_display_candles_preserve_ohlc_gaps_and_closed_boundary():
    observations = [
        CandleReadModel(
            st_ts=0, en_ts=300, open=1001, high=1037, low=999, close=1021
        ),
        CandleReadModel(
            st_ts=300, en_ts=600, open=1021, high=1059, low=1011, close=1039
        ),
        CandleReadModel(
            st_ts=3600, en_ts=3900, open=1061, high=1073, low=1041, close=1053
        ),
        CandleReadModel(
            st_ts=5400, en_ts=5700, open=1053, high=1087, low=1049, close=1071
        ),
    ]
    card = AssetChartCard(
        asset=ChartAsset(
            id=1, code=AssetCode.USD, title="Dollar", primary_color="#16a34a"
        ),
        chart=CandleChartModel(
            timeframe=TimeFrame.FIVE_MINUTE,
            candles=observations,
            from_timestamp=0,
            to_timestamp=5700,
        ),
        style=AssetChartPolicy(candle_interval_seconds=1800),
        timezone="Asia/Tehran",
        caption="Chart",
    )
    series = ChartSeries().candles(card)
    assert series.interval_seconds == 1800
    assert [row.st_ts for row in series.candles] == [0, 3600]
    assert series.candles[0].model_dump() == {
        "open": 1001,
        "high": 1059,
        "low": 999,
        "close": 1039,
        "st_ts": 0,
        "en_ts": 1800,
    }
    assert series.candles[1].close == 1053
    assert card.chart.candles == observations
