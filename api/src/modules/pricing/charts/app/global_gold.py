from html import escape

from portal_contracts.configuration import PortalConfiguration
from src.modules.pricing.charts.domain.models import (
    ChartQuote,
    GlobalGoldChartCard,
    GlobalGoldInstrument,
)
from src.modules.pricing.charts.interfaces import IGlobalGoldSeries
from src.modules.pricing.engine.interfaces import ICacheReaderService
from src.modules.pricing.sources.interfaces import ISourceService
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode
from src.shared.dates import as_utc, utc_now


class GlobalGoldChartQuery:
    def __init__(
        self,
        readings: ICacheReaderService,
        sources: ISourceService,
        series: IGlobalGoldSeries,
        settings: PortalConfiguration,
    ):
        self.readings, self.sources, self.series, self.settings = (
            readings,
            sources,
            series,
            settings,
        )

    async def get(self) -> GlobalGoldChartCard | None:
        now = utc_now()
        rows = await self.readings.get_many_by_symbols([SymbolCode.XAU_OUNCE])
        sources = {
            s.id: s for s in await self.sources.get_all() if s.is_active
        }
        candidates = [
            row
            for row in rows.get(SymbolCode.XAU_OUNCE, ())
            if row.source_id in sources
            and row.currency == CurrencyType.USD
            and row.price > 0
            and not row.is_closed
            and 0
            <= (now - as_utc(row.priced_at)).total_seconds()
            <= self.settings.market.max_age_seconds
        ]
        if not candidates:
            return None
        quote = max(
            candidates, key=lambda x: (as_utc(x.priced_at), x.source_id)
        )
        end = int(now.timestamp())
        start = end - 43200
        chart = await self.series.read(quote.source_id, start, end)
        chart = chart.model_copy(
            update={
                "candles": [
                    row
                    for row in chart.candles
                    if 0 < row.low <= min(row.open, row.close)
                    and max(row.open, row.close) <= row.high
                ]
            }
        )
        if not chart.candles:
            return None
        source = sources[quote.source_id]
        unchanged = (
            len(chart.candles) >= 2
            and len({(c.low, c.high) for c in chart.candles}) == 1
            and all(c.low == c.high for c in chart.candles)
        )
        status = (
            "قیمت منبع در این بازه بدون تغییر بوده است" if unchanged else ""
        )
        style = self.settings.market.charts.model_copy(
            update={
                "window": "daily",
                "unit_label": "USD / troy oz",
                "recorded_label": "آخرین دریافت از منبع",
                "caption": "اونس جهانی طلا؛ دلار به‌ازای هر اونس تروا",
                "footer": status or "کندل‌های بسته‌شدهٔ ثبت‌شده · ۱۲ ساعت اخیر",
                "candle_interval_seconds": 300,
                "asset_display_symbols": {"xau_ounce": "XAU / USD"},
                "asset_labels": {"xau_ounce": "اونس جهانی طلا"},
                "asset_logos": {"xau_ounce": "gold.svg"},
                "window_labels": {"daily": "۱۲ ساعت اخیر"},
            }
        )
        return GlobalGoldChartCard(
            instrument=GlobalGoldInstrument(source_id=source.id),
            chart=chart,
            style=style,
            timezone=self.settings.portal.timezone,
            quote=ChartQuote(price=quote.price, priced_at=quote.priced_at),
            caption="<b>🌍 اونس جهانی طلا · XAU/USD</b>\n"
            "دلار به‌ازای هر اونس تروا · ۱۲ ساعت اخیر\n"
            "منبع: "
            + escape(source.title)
            + "\n"
            + escape(source.website_url)
            + ("\n⏸ " + status if status else "")
            + "\nزمان نمایش‌داده‌شده، زمان دریافت قیمت از منبع است."
            + "\n📊 TradingView Lightweight Charts™ · © TradingView, Inc.",
        )
