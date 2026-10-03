from dishka import Provider, Scope, alias, provide
from papilio_tasks.apps.schedulers.redis import SchedulerApplication
from taskiq import ScheduleSource

from src.modules.pricing.calculator.app.calculators import (
    BubbleCalculatorService,
    CalculatorService,
)
from src.modules.pricing.calculator.app.readers import CacheReaderService
from src.modules.pricing.calculator.app.schedulers import (
    BubbleSchedulerService,
    SchedulerService,
)
from src.modules.pricing.calculator.app.schedules import ReconcileSchedules
from src.modules.pricing.calculator.app.services import (
    SymbolConverterService,
)
from src.modules.pricing.calculator.infra.cache import (
    AssetPriceCache,
    BubbleCache,
)
from src.modules.pricing.calculator.infra.readers import (
    AssetReader,
    BubbleReader,
    SourceReader,
    SwitchOrderReader,
    SymbolReader,
)
from src.modules.pricing.calculator.infra.schedules import ScheduleReader
from src.modules.pricing.calculator.interfaces import (
    IBubbleCalculatorService,
    IBubbleSchedulerService,
    ICacheReaderService,
    ICalculatorService,
    IReconcileSchedules,
    ISchedulerService,
    ISymbolConverterService,
)
from src.modules.pricing.calculator.tasks.schedulers.bubble import (
    CalculateBubbleTask,
)
from src.modules.pricing.calculator.tasks.schedulers.price import (
    CalculateAssetTask,
    CalculateUsdTask,
    RepriceAssetTask,
)
from src.modules.pricing.calculator.tasks.schedulers.reconcile import (
    ReconcileSchedulesTask,
)


class CalculatorProvider(Provider):
    scope = Scope.REQUEST

    schedule_reader = provide(ScheduleReader)
    reconcile_task = provide(ReconcileSchedulesTask)

    @provide
    def reconcile_schedules(
        self, reader: ScheduleReader, app: SchedulerApplication
    ) -> ReconcileSchedules:
        return ReconcileSchedules(
            reader,
            app.source,
            CalculateAssetTask.task().task_name,
            CalculateBubbleTask.task().task_name,
            CalculateUsdTask.task().task_name,
        )

    asset_price_cache = provide(AssetPriceCache, scope=Scope.APP)
    bubble_cache = provide(BubbleCache, scope=Scope.APP)
    cache_reader_service = provide(
        CacheReaderService, provides=ICacheReaderService, scope=Scope.APP
    )
    symbol_reader = provide(SymbolReader)
    asset_reader = provide(AssetReader)
    bubble_reader = provide(BubbleReader)
    switch_order_reader = provide(SwitchOrderReader)
    source_reader = provide(SourceReader)
    symbol_converter_service = provide(
        SymbolConverterService, provides=ISymbolConverterService
    )
    calculator_service = provide(
        CalculatorService, provides=ICalculatorService
    )
    bubble_calculator_service = provide(
        BubbleCalculatorService, provides=IBubbleCalculatorService
    )

    @provide(scope=Scope.APP)
    def scheduler_service(self, source: ScheduleSource) -> ISchedulerService:
        return SchedulerService(source, CalculateAssetTask.task().task_name)

    @provide(scope=Scope.APP)
    def bubble_scheduler_service(
        self, source: ScheduleSource
    ) -> IBubbleSchedulerService:
        return BubbleSchedulerService(
            source, CalculateBubbleTask.task().task_name
        )

    calculatebubbletask = provide(CalculateBubbleTask, scope=Scope.REQUEST)
    calculateusdtask = provide(CalculateUsdTask, scope=Scope.REQUEST)
    calculateassettask = provide(CalculateAssetTask, scope=Scope.REQUEST)
    repriceassettask = provide(RepriceAssetTask, scope=Scope.REQUEST)

    reconcile_contract = alias(
        ReconcileSchedules, provides=IReconcileSchedules
    )
