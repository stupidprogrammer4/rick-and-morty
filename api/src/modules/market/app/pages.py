import re
from decimal import ROUND_HALF_UP, Decimal
from html import escape, unescape
from zoneinfo import ZoneInfo

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import PublicationPage, PublicationPages
from portal_contracts.enums import Category
from portal_contracts.presentation import PortalPresentation
from src.modules.market.domain.dtos import MarketSnapshot, Quote


class MarketPageRenderer:
    def __init__(
        self, settings: PortalConfiguration, presentation: PortalPresentation
    ):
        self.settings = settings
        self.presentation = presentation

    def preview(self, pages: PublicationPages) -> str:
        text = unescape(re.sub(r"<[^>]+>", "", pages.items[0].text))
        counter = pages.page_label.replace("{page}", "1").replace(
            "{total}", str(len(pages.items))
        )
        return f"{text}\n\n{counter}"

    def rate(self, quote: Quote, index: int) -> str:
        p = self.presentation
        divisor = Decimal(10) if quote.currency == "IRR" else Decimal(1)
        precision = Decimal("0.01") if quote.currency == "USD" else Decimal(1)
        buy = (
            (
                quote.buy_amount
                if quote.buy_amount is not None
                else quote.amount
            )
            / divisor
        ).quantize(precision, rounding=ROUND_HALF_UP)
        sell = (
            (
                quote.sell_amount
                if quote.sell_amount is not None
                else quote.amount
            )
            / divisor
        ).quantize(precision, rounding=ROUND_HALF_UP)
        value = (
            f"{escape(p.market_buy_emoji)} {escape(p.market_buy_label)} "
            f"<b>{buy:,}</b>\n"
            f"{escape(p.market_sell_emoji)} {escape(p.market_sell_label)} "
            f"<b>{sell:,}</b>"
            if buy != sell
            else f"{escape(p.market_source_emoji)} "
            f"{escape(p.market_single_label)} <b>{buy:,}</b>"
        )
        stamp = quote.quoted_at.astimezone(
            ZoneInfo(self.settings.portal.timezone)
        ).strftime("%Y-%m-%d · %H:%M")
        clock = (
            p.quote_time_label
            if quote.timestamp_kind == "source"
            else p.fetch_time_label
        )
        name = escape(quote.source_name or quote.label)
        url = escape(str(quote.source_url), quote=True)
        return (
            f'{index}. <a href="{url}"><b>{name}</b></a>\n'
            f"{value}\n<i>{escape(clock)} · {stamp}</i>"
        )

    def render(self, snapshot: MarketSnapshot) -> PublicationPages:
        p = self.presentation
        style = p.posts[Category.MARKET]
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
        pages = []
        width = p.market_sources_per_page
        for (symbol, _, currency, _, label), quotes in groups.items():
            decoration = p.asset_styles.get(symbol)
            title = f"{decoration.emoji} {label}" if decoration else label
            unit = (
                p.market_usd_label
                if currency == "USD"
                else p.market_toman_label
            )
            for start in range(0, len(quotes), width):
                entries = [
                    self.rate(q, start + offset + 1)
                    for offset, q in enumerate(quotes[start : start + width])
                ]
                body = (
                    f"<b>{escape(style.heading)}</b>\n"
                    f"{escape(style.separator)}\n\n"
                    f"<b>{escape(title)}</b>\n<i>{escape(unit)}</i>\n\n"
                    + "\n\n".join(entries)
                    + f"\n\n{escape(style.separator)}\n"
                    + f"{escape(style.footer)}\n\n"
                    + (escape(decoration.hashtag) + "\n" if decoration else "")
                    + escape(style.hashtags)
                )
                if len(body) > p.maximum_post_characters:
                    raise ValueError(
                        "Market page exceeds the configured post limit"
                    )
                pages.append(PublicationPage(title=title, text=body))
        return PublicationPages(
            items=pages,
            previous_label=p.previous_page_label,
            next_label=p.next_page_label,
            page_label=p.page_label,
        )
