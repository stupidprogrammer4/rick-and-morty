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
)
from src.modules.pricing.charts.infra.browser import (
    BrowserImageRenderer,
    ChartAssets,
)
from src.shared.dates import as_utc


class AssetChartRenderer:
    def __init__(self, browser: BrowserImageRenderer, assets: ChartAssets):
        self.browser = browser
        self.assets = assets

    @staticmethod
    @lru_cache(maxsize=3)
    def template(name: str) -> str:
        return (Path(__file__).parent / "templates" / name).read_text()

    async def render(self, card: AssetChartCard) -> bytes:
        document = self.document(card)
        result = await self.browser.render(document)
        return result

    def document(self, card: AssetChartCard) -> BrowserImageRequest:
        style = card.style
        code = card.asset.code.value
        rows = sorted(card.chart.candles, key=lambda row: row.st_ts)
        aggregated = ChartSeries().candles(card)
        candles = [
            {
                "time": row.en_ts,
                "open": row.open / 10,
                "high": row.high / 10,
                "low": row.low / 10,
                "close": row.close / 10,
            }
            for row in aggregated.candles
        ]
        points = []
        previous = None
        for row in rows:
            if previous is not None and row.st_ts > previous:
                points.append({"x": previous * 1000 + 1, "y": None})
            points.append({"x": row.en_ts * 1000, "y": row.close / 10})
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
        decimals = int(
            bool(latest is not None and latest % 10)
            or any(
                value % 10
                for row in rows
                for value in (row.open, row.high, row.low, row.close)
            )
        )
        logo_name = style.asset_logos.get(code)
        logo = self.assets.logo(logo_name) if logo_name else ""
        accent = card.asset.primary_color
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
            "TITLE": style.asset_labels.get(code, card.asset.title),
            "PRICE_LABEL": style.price_label,
            "PRICE": f"{Decimal(latest) / 10:,.1f}".removesuffix(".0")
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
                "latest": latest / 10 if latest is not None else None,
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
