from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.presentation import PortalPresentation
from src.modules.pricing.reports.domain.dtos import MarketSnapshot, Quote


class MarketReportRenderer:
    def __init__(
        self, settings: PortalConfiguration, presentation: PortalPresentation
    ):
        self.settings = settings
        self.presentation = presentation

    def render(self, snapshot: MarketSnapshot) -> str:
        if snapshot.mode == "sources":
            return self.sources(snapshot)
        lines = []
        zone = ZoneInfo(self.settings.portal.timezone)
        for quote in snapshot.quotes:
            style = self.presentation.asset_styles.get(quote.symbol)
            label = f"{style.emoji} {quote.label}" if style else quote.label
            stamp = quote.quoted_at.astimezone(zone).strftime("%Y-%m-%d %H:%M")
            time_label = (
                self.presentation.quote_time_label
                if quote.timestamp_kind == "source"
                else self.presentation.fetch_time_label
            )
            lines.append(
                f"{label}: {quote.toman():,} تومان\n"
                f"{time_label}: {stamp}\n"
                f"{self.presentation.source_label}: "
                + " · ".join(
                    str(url) for url in (quote.sources or [quote.source_url])
                )
                + (f"\n{style.hashtag}" if style else "")
            )
        return "\n\n".join(lines)

    def sources(self, snapshot: MarketSnapshot) -> str:
        groups: dict[tuple[str, str, str, str | None, str], list[Quote]] = {}
        for quote in snapshot.quotes:
            key = (
                quote.symbol,
                quote.basis,
                quote.currency,
                quote.purity,
                quote.label,
            )
            groups.setdefault(key, []).append(quote)
        blocks = []
        zone = ZoneInfo(self.settings.portal.timezone)
        for (symbol, _, currency, _, label), rows in groups.items():
            style = self.presentation.asset_styles.get(symbol)
            heading = f"{style.emoji} {label}" if style else label
            unit = (
                self.presentation.market_usd_label
                if currency == "USD"
                else self.presentation.market_toman_label
            )
            lines = [heading + f" ({unit})"]
            for quote in rows:
                divisor = (
                    Decimal(10) if quote.currency == "IRR" else Decimal(1)
                )
                precision = (
                    Decimal("0.01") if quote.currency == "USD" else Decimal(1)
                )
                buy = (
                    quote.buy_amount
                    if quote.buy_amount is not None
                    else quote.amount
                ) / divisor
                sell = (
                    quote.sell_amount
                    if quote.sell_amount is not None
                    else quote.amount
                ) / divisor
                buying = buy.quantize(precision, rounding=ROUND_HALF_UP)
                selling = sell.quantize(precision, rounding=ROUND_HALF_UP)
                value = (
                    f"{self.presentation.market_buy_label} {buying:,} · "
                    f"{self.presentation.market_sell_label} {selling:,}"
                    if buying != selling
                    else f"{self.presentation.market_single_label} {buying:,}"
                )
                stamp = quote.quoted_at.astimezone(zone).strftime(
                    "%Y-%m-%d %H:%M"
                )
                clock = (
                    self.presentation.quote_time_label
                    if quote.timestamp_kind == "source"
                    else self.presentation.fetch_time_label
                )
                lines.append(
                    f"{self.presentation.market_source_emoji} "
                    f"{quote.source_name}: {value}\n{clock} {stamp}"
                )
            lines.append(
                self.presentation.source_label
                + ": "
                + " · ".join(str(q.source_url) for q in rows)
            )
            if style:
                lines.append(style.hashtag)
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
