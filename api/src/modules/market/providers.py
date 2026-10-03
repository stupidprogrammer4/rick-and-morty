from dishka import Provider, Scope, provide

from portal_contracts.configuration import PortalConfiguration
from src.modules.market.app.commands import (
    MarketDraftCommands,
    MarketPublicationQuery,
)
from src.modules.market.app.pages import MarketPageRenderer
from src.modules.market.app.queries import MarketQuery
from src.modules.market.app.renderer import MarketReportRenderer
from src.modules.market.app.services import MarketSnapshotService
from src.modules.market.app.source_quotes import SourceMarketPriceProvider
from src.modules.market.infra.auryx import AuryxPriceProvider
from src.modules.market.infra.mysql import MarketSnapshotRepository
from src.modules.market.infra.site import OwnerSitePriceProvider
from src.modules.market.interfaces import (
    IMarketDraftCommands,
    IMarketPublicationQuery,
    IMarketQuery,
    IMarketSnapshotService,
    IPriceProvider,
)


class MarketProvider(Provider):
    scope = Scope.REQUEST
    talamala_prices = provide(OwnerSitePriceProvider)
    auryx_prices = provide(AuryxPriceProvider)
    source_prices = provide(SourceMarketPriceProvider)

    @provide
    def prices(
        self,
        settings: PortalConfiguration,
        talamala: OwnerSitePriceProvider,
        auryx: AuryxPriceProvider,
        sources: SourceMarketPriceProvider,
    ) -> IPriceProvider:
        if (
            settings.market.backend == "auryx"
            and settings.market.report_mode == "sources"
        ):
            return sources
        return auryx if settings.market.backend == "auryx" else talamala

    market = provide(MarketQuery, provides=IMarketQuery)
    snapshot_repo = provide(MarketSnapshotRepository)
    snapshot_service = provide(
        MarketSnapshotService, provides=IMarketSnapshotService
    )
    renderer = provide(MarketReportRenderer)
    pages = provide(MarketPageRenderer)
    draft_commands = provide(
        MarketDraftCommands, provides=IMarketDraftCommands
    )
    publication_query = provide(
        MarketPublicationQuery, provides=IMarketPublicationQuery
    )
