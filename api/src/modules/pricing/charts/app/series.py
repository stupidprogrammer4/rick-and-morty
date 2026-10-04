from datetime import datetime
from itertools import groupby
from zoneinfo import ZoneInfo

from src.modules.pricing.charts.domain.models import (
    AssetChartCard,
    ChartCandleSeries,
)


class ChartSeries:
    def bucket(
        self, timestamp: int, step: int, zone: ZoneInfo
    ) -> tuple[int, int]:
        offset = datetime.fromtimestamp(timestamp, zone).utcoffset()
        if offset is None:
            raise ValueError("Chart timezone offset is unavailable")
        seconds = int(offset.total_seconds())
        return (timestamp + seconds) // step, seconds

    def candles(self, card: AssetChartCard) -> ChartCandleSeries:
        step = max(
            card.style.candle_interval_seconds, card.chart.timeframe.seconds
        )
        native = card.chart.timeframe.seconds
        step = ((step + native - 1) // native) * native
        zone = ZoneInfo(card.timezone)
        rows = sorted(card.chart.candles, key=lambda row: row.st_ts)
        result = []
        for (bucket, offset), values in groupby(
            rows, key=lambda row: self.bucket(row.st_ts, step, zone)
        ):
            group = list(values)
            end = (bucket + 1) * step - offset
            if end > card.chart.to_timestamp:
                continue
            result.append(
                group[0].model_copy(
                    update={
                        "st_ts": bucket * step - offset,
                        "en_ts": end,
                        "high": max(row.high for row in group),
                        "low": min(row.low for row in group),
                        "close": group[-1].close,
                    }
                )
            )
        return ChartCandleSeries(interval_seconds=step, candles=result)
