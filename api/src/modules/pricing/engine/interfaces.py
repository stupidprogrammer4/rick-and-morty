from collections.abc import Awaitable
from typing import Mapping, Protocol, Sequence

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.engine.domain.context import (
    CFGContext,
    SourceContext,
)
from src.modules.pricing.engine.domain.models import (
    AggregatedPriceModel,
    PricedSourceModel,
    SymbolAggModel,
)
from src.modules.pricing.engine.domain.quotes import (
    SourceQuote,
    SupplierSourceQuote,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.sources.domain.models import (
    SourceBubbleModel,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode


class ICFGReaderService(Protocol):
    def read_context(self) -> Awaitable[CFGContext]: ...


class ICrawlerService(Protocol):
    def crawl(
        self, cfg: CFGContext
    ) -> Awaitable[tuple[SourceQuote, SourceQuote]]: ...


class ICacheFlusherService(Protocol):
    def flush_results(
        self, cfg: CFGContext, quotes: SourceQuote
    ) -> Awaitable[int]: ...


class IPersistFlusherService(Protocol):
    def flush_errors(
        self,
        cfg: CFGContext,
        quotes: SourceQuote,
    ) -> Awaitable[int]: ...


class IRunnerService(Protocol):
    def run(self) -> Awaitable[bool]: ...


class ISelectionService(Protocol):
    def record(
        self,
        symbols: Mapping[int, SymbolCode],
        verdicts: Sequence[PricedSourceModel],
    ) -> Awaitable[int]: ...


class IPushedFlusherService(Protocol):
    def flush_supplier(
        self,
        source: SourceContext,
        symbols: Mapping[SymbolCode, int],
        quotes: Sequence[SupplierSourceQuote],
    ) -> Awaitable[int]: ...


class ICacheReaderService(Protocol):
    def get_by_symbol(
        self, symbol: SymbolCode
    ) -> Awaitable[Sequence[PricedSourceModel]]: ...

    def get_many_by_symbols(
        self, symbols: Sequence[SymbolCode]
    ) -> Awaitable[dict[SymbolCode, Sequence[PricedSourceModel]]]: ...

    def get_all(
        self,
    ) -> Awaitable[dict[SymbolCode, Sequence[PricedSourceModel]]]: ...

    def get_by_source_id(
        self, source_id: int
    ) -> Awaitable[Sequence[PricedSourceModel]]: ...

    def get_by_source_ids(
        self, source_ids: Sequence[int]
    ) -> Awaitable[Sequence[PricedSourceModel]]: ...

    def get_bubbles_by_asset(
        self, code: AssetCode
    ) -> Awaitable[Sequence[SourceBubbleModel]]: ...

    def get_all_bubbles(
        self,
    ) -> Awaitable[dict[AssetCode, Sequence[SourceBubbleModel]]]: ...


class IAggregatorService(Protocol):
    def agg(self, code: SymbolCode) -> Awaitable[AggregatedPriceModel]: ...

    def stats(self, code: SymbolCode) -> Awaitable[SymbolAggModel]: ...


class IPushRunnerService(Protocol):
    def run(
        self, code: SourceCode, quotes: Sequence[SupplierSourceQuote]
    ) -> Awaitable[bool]: ...
