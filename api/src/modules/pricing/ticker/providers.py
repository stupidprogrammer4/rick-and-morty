from dishka import Provider, Scope, provide

from src.modules.pricing.ticker.app.services import (
    BubbleSnapshotService,
    BubbleTickerService,
    PriceSnapshotService,
    PriceTickerService,
    SourceBubbleSnapshotService,
    SourceBubbleTickerService,
    SourcePriceSnapshotService,
    SourcePriceTickerService,
)
from src.modules.pricing.ticker.infra.mysql import (
    BubbleTickerRepository,
    PriceTickerRepository,
    SourceBubbleTickerRepository,
    SourcePriceTickerRepository,
)
from src.modules.pricing.ticker.infra.readers import (
    BubbleTickerReader,
    PriceTickerReader,
    SourceBubbleTickerReader,
    SourcePriceTickerReader,
)
from src.modules.pricing.ticker.interfaces import (
    IBubbleSnapshotService,
    IBubbleTickerService,
    IPriceSnapshotService,
    IPriceTickerService,
    ISourceBubbleSnapshotService,
    ISourceBubbleTickerService,
    ISourcePriceSnapshotService,
    ISourcePriceTickerService,
)
from src.modules.pricing.ticker.tasks.schedulers.snapshot import (
    SnapshotBubblesTask,
    SnapshotPricesTask,
    SnapshotSourceBubblesTask,
    SnapshotSourcePricesTask,
)


class TickerProvider(Provider):
    scope = Scope.REQUEST

    price_reader = provide(PriceTickerReader)
    bubble_reader = provide(BubbleTickerReader)
    source_price_reader = provide(SourcePriceTickerReader)
    source_bubble_reader = provide(SourceBubbleTickerReader)

    price_ticker_repo = provide(PriceTickerRepository)
    source_price_ticker_repo = provide(SourcePriceTickerRepository)
    price_ticker_service = provide(
        PriceTickerService, provides=IPriceTickerService
    )
    source_price_ticker_service = provide(
        SourcePriceTickerService, provides=ISourcePriceTickerService
    )
    price_snapshot_service = provide(
        PriceSnapshotService, provides=IPriceSnapshotService
    )
    source_price_snapshot_service = provide(
        SourcePriceSnapshotService, provides=ISourcePriceSnapshotService
    )
    bubble_ticker_repo = provide(BubbleTickerRepository)
    bubble_snapshot_service = provide(
        BubbleSnapshotService, provides=IBubbleSnapshotService
    )
    bubble_ticker_service = provide(
        BubbleTickerService, provides=IBubbleTickerService
    )
    source_bubble_ticker_repo = provide(SourceBubbleTickerRepository)
    source_bubble_snapshot_service = provide(
        SourceBubbleSnapshotService, provides=ISourceBubbleSnapshotService
    )
    source_bubble_ticker_service = provide(
        SourceBubbleTickerService, provides=ISourceBubbleTickerService
    )
    snapshotpricestask = provide(SnapshotPricesTask, scope=Scope.REQUEST)
    snapshotsourcepricestask = provide(
        SnapshotSourcePricesTask, scope=Scope.REQUEST
    )
    snapshotbubblestask = provide(SnapshotBubblesTask, scope=Scope.REQUEST)
    snapshotsourcebubblestask = provide(
        SnapshotSourceBubblesTask, scope=Scope.REQUEST
    )
