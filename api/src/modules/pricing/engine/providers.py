from dishka import Provider, Scope, alias, provide

from src.modules.pricing.engine.app.aggregators import AggregatorService
from src.modules.pricing.engine.app.flushers import (
    CacheFlusherService,
    PersistFlusherService,
    PushedFlusherService,
    SelectionService,
)
from src.modules.pricing.engine.app.readers import (
    CacheReaderService,
    CFGReaderService,
)
from src.modules.pricing.engine.app.runners import (
    PushRunnerService,
    RunnerService,
)
from src.modules.pricing.engine.app.services import CrawlerService
from src.modules.pricing.engine.infra.cache import (
    BubbleSourceCache,
    SourcePriceCache,
    SourceSelectionCache,
)
from src.modules.pricing.engine.infra.readers import (
    AssetReader,
    SourceReader,
    SymbolReader,
)
from src.modules.pricing.engine.interfaces import (
    IAggregatorService,
    ICacheFlusherService,
    ICacheReaderService,
    ICFGReaderService,
    ICrawlerService,
    IPersistFlusherService,
    IPushedFlusherService,
    IPushRunnerService,
    IRunnerService,
    ISelectionService,
)
from src.modules.pricing.engine.tasks.schedulers.crawl import (
    CrawlAllSourcesTask,
)
from src.modules.pricing.engine.tasks.schedulers.price import (
    PersistSupplierPrice,
)


class EngineProvider(Provider):
    persist_supplier = provide(PersistSupplierPrice, scope=Scope.REQUEST)
    source_price_cache = provide(SourcePriceCache, scope=Scope.APP)
    bubble_source_cache = provide(BubbleSourceCache, scope=Scope.APP)
    source_selection_cache = provide(SourceSelectionCache, scope=Scope.APP)
    selection_service = provide(
        SelectionService, provides=ISelectionService, scope=Scope.APP
    )
    crawler_service = provide(
        CrawlerService, provides=ICrawlerService, scope=Scope.APP
    )
    cache_flusher_service = provide(
        CacheFlusherService, provides=ICacheFlusherService, scope=Scope.REQUEST
    )
    cache_reader_service = provide(
        CacheReaderService, provides=ICacheReaderService, scope=Scope.APP
    )
    runner_service = provide(
        RunnerService, provides=IRunnerService, scope=Scope.APP
    )
    pushed_flusher_service = provide(
        PushedFlusherService,
        provides=IPushedFlusherService,
        scope=Scope.REQUEST,
    )
    push_runner_service = provide(PushRunnerService, scope=Scope.APP)

    aggregator_service = provide(
        AggregatorService, provides=IAggregatorService, scope=Scope.REQUEST
    )
    asset_reader = provide(AssetReader, scope=Scope.REQUEST)
    source_reader = provide(SourceReader, scope=Scope.REQUEST)
    symbol_reader = provide(SymbolReader, scope=Scope.REQUEST)
    cfg_reader_service = provide(
        CFGReaderService, provides=ICFGReaderService, scope=Scope.REQUEST
    )
    persist_flusher_service = provide(
        PersistFlusherService,
        provides=IPersistFlusherService,
        scope=Scope.REQUEST,
    )
    crawlallsourcestask = provide(CrawlAllSourcesTask, scope=Scope.REQUEST)

    push_runner_service_contract = alias(
        PushRunnerService, provides=IPushRunnerService
    )
