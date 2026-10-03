from zoneinfo import ZoneInfo

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.presentation import PortalPresentation
from src.modules.market.domain.dtos import MarketSnapshot


class MarketReportRenderer:
    def __init__(
        self, settings: PortalConfiguration, presentation: PortalPresentation
    ):
        self.settings = settings
        self.presentation = presentation

    def render(self, snapshot: MarketSnapshot) -> str:
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
