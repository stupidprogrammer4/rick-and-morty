from dishka import Provider, Scope, provide

from src.modules.market.app.commands import (
    MarketDraftCommands,
    MarketPublicationQuery,
)
from src.modules.market.app.queries import MarketQuery
from src.modules.market.app.renderer import MarketReportRenderer
from src.modules.market.app.services import MarketSnapshotService
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
    prices = provide(OwnerSitePriceProvider, provides=IPriceProvider)
    market = provide(MarketQuery, provides=IMarketQuery)
    snapshot_repo = provide(MarketSnapshotRepository)
    snapshot_service = provide(
        MarketSnapshotService, provides=IMarketSnapshotService
    )
    renderer = provide(MarketReportRenderer)
    draft_commands = provide(
        MarketDraftCommands, provides=IMarketDraftCommands
    )
    publication_query = provide(
        MarketPublicationQuery, provides=IMarketPublicationQuery
    )
