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
            stamp = quote.quoted_at.astimezone(zone).strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"{quote.label}: {quote.toman():,} تومان\n"
                f"{self.presentation.quote_time_label}: {stamp}\n"
                f"{self.presentation.source_label}: {quote.source_url}"
            )
        return "\n\n".join(lines)
