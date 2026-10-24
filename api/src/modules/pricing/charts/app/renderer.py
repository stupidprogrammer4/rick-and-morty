import asyncio
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from src.modules.pricing.charts.app.series import ChartSeries
from src.modules.pricing.charts.domain.models import (
    AssetChartCard,
    BrowserImageRequest,
    GlobalGoldChartCard,
)
from src.modules.pricing.charts.infra.browser import (
    BrowserImageRenderer,
    ChartAssets,
)
from src.modules.pricing.charts.interfaces import IChartImageCache
from src.shared.dates import as_utc


class AssetChartRenderer:
    def __init__(
        self,
        browser: BrowserImageRenderer,
        assets: ChartAssets,
        cache: IChartImageCache | None = None,
    ):
        self.browser = browser
        self.assets = assets
        self.cache = cache
        self.capacity = asyncio.Lock()

    @staticmethod
    @lru_cache(maxsize=3)
    def template(name: str) -> str:
        return (Path(__file__).parent / "templates" / name).read_text()

    async def render(
        self, card: AssetChartCard | GlobalGoldChartCard
    ) -> bytes:
        document = self.document(card)
        if self.cache is None:
            return await self.browser.render(document)
        key = hashlib.sha256(document.model_dump_json().encode()).hexdigest()
        image = await self.cache.get(key)
        if image is not None:
            return image
        # Coalesce concurrent local misses without launching more browsers.
        async with self.capacity:
            image = await self.cache.get(key)
            if image is None:
                image = await self.browser.render(document)
                await self.cache.put(key, image)
            return image

    def document(
        self, card: AssetChartCard | GlobalGoldChartCard
    ) -> BrowserImageRequest:
        style = card.style
        identity = (
            card.asset if isinstance(card, AssetChartCard) else card.instrument
        )
        code = identity.code.value
        divisor = card.price_divisor
        rows = sorted(card.chart.candles, key=lambda row: row.st_ts)
        aggregated = ChartSeries().candles(card)
        candles = [
            {
                "time": row.en_ts,
                "open": row.open / divisor,
                "high": row.high / divisor,
                "low": row.low / divisor,
                "close": row.close / divisor,
            }
            for row in aggregated.candles
        ]
        points = []
        previous = None
        for row in rows:
            if previous is not None and row.st_ts > previous:
                points.append({"x": previous * 1000 + 1, "y": None})
            points.append({"x": row.en_ts * 1000, "y": row.close / divisor})
            previous = row.en_ts
        quote = card.quote
        zone = ZoneInfo(card.timezone)
        latest = quote.price if quote else rows[-1].close if rows else None
        recorded = (
            as_utc(quote.priced_at).astimezone(zone)
            if quote
            else datetime.fromtimestamp(rows[-1].en_ts, zone)
            if rows
            else None
        )
        decimals = (
            2
            if divisor == 100
            else int(
                bool(latest is not None and latest % divisor)
                or any(
                    value % divisor
                    for row in rows
                    for value in (row.open, row.high, row.low, row.close)
                )
            )
        )
        logo_name = style.asset_logos.get(code)
        logo = self.assets.logo(logo_name) if logo_name else ""
        accent = identity.primary_color
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            accent = style.rising
        css = self.template("card.css")
        replacements = {
            "FONT": self.assets.font(),
            "BACKGROUND": style.background,
            "FOREGROUND": style.foreground,
            "ACCENT": accent,
            "PANEL": style.panel_background or style.background,
        }
        for key, value in replacements.items():
            css = css.replace("__" + key + "__", value)
        html = self.template("card.html")
        fields = {
            "LOGO": logo,
            "SYMBOL": style.asset_display_symbols.get(code, code.upper()),
            "WINDOW": style.window_labels.get(style.window, style.window),
            "TITLE": style.asset_labels.get(code, identity.title),
            "PRICE_LABEL": style.price_label,
            "PRICE": (
                f"{Decimal(latest) / divisor:,.2f}"
                if divisor == 100
                else f"{Decimal(latest) / divisor:,.1f}".removesuffix(".0")
            )
            if latest is not None
            else "—",
            "UNIT": style.unit_label,
            "RECORDED": style.recorded_label,
            "TIME": recorded.strftime("%Y-%m-%d %H:%M") if recorded else "—",
            "OHLC": style.ohlc_label
            + " · "
            + str(aggregated.interval_seconds // 60)
            + "m",
            "LINE": style.line_label,
            "EMPTY": style.empty_label,
            "FOOTER": style.footer,
            "ZONE": card.timezone,
        }
        for key, value in fields.items():
            html = html.replace("__" + key + "__", escape(value, quote=True))
        data = json.dumps(
            {
                "candles": candles,
                "latest": latest / divisor if latest is not None else None,
                "line": points,
                "decimals": decimals,
                "style": style.model_dump(mode="json"),
                "timezone": card.timezone,
            },
            ensure_ascii=False,
        ).replace("<", "\\u003c")
        html = html.replace("__CSS__", css).replace("__DATA__", data)
        return BrowserImageRequest(
            html=html,
            script=self.template("card.js"),
            width=style.width,
            height=style.height,
        )
