from portal_contracts.configuration import PortalConfiguration
from portal_contracts.presentation import PortalPresentation
from src.modules.market.app.renderer import MarketReportRenderer
from src.modules.market.domain.dtos import MarketSnapshot, validate_freshness
from src.modules.market.interfaces import IPriceProvider
from src.shared.dates import utc_now


class MarketQuery:
    def __init__(
        self,
        provider: IPriceProvider,
        settings: PortalConfiguration,
        presentation: PortalPresentation,
        renderer: MarketReportRenderer,
    ):
        self.provider = provider
        self.settings = settings
        self.presentation = presentation
        self.renderer = renderer

    async def snapshot(self) -> MarketSnapshot:
        if not self.settings.market.enabled:
            raise ValueError("بازار از تنظیمات غیرفعال شده.")
        result = await self.provider.fetch()
        validate_freshness(
            result,
            utc_now(),
            self.settings.market.max_age_seconds,
            self.settings.market.future_skew_seconds,
        )
        return result

    async def report(self) -> str:
        snapshot = await self.snapshot()
        return self.renderer.render(snapshot)
