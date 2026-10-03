from collections import defaultdict
from typing import Mapping, Sequence

from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.transaction import transaction
from papilio.utils import dates as date_utils

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.candle.interfaces import ISourceWindowService
from src.modules.pricing.engine.app.crawlers.bubble import BUBBLE_FETCHERS
from src.modules.pricing.engine.app.crawlers.global_market import (
    GLOBAL_FETCHERS,
)
from src.modules.pricing.engine.app.crawlers.iran_market import IRAN_FETCHERS
from src.modules.pricing.engine.app.crawlers.supplier import (
    SUPPLIER_FETCHERS,
)
from src.modules.pricing.engine.app.helpers.quotes import (
    GlobalMarketPriceHelper,
    IranMarketPriceHelper,
    SupplierMarketPriceHelper,
)
from src.modules.pricing.engine.domain.context import (
    CFGContext,
    SourceContext,
)
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
    SourceSelectionModel,
)
from src.modules.pricing.engine.domain.quotes import (
    ErrorQuote,
    SourceQuote,
    SupplierSourceQuote,
)
from src.modules.pricing.engine.infra.cache import (
    BubbleSourceCache,
    SourcePriceCache,
    SourceSelectionCache,
)
from src.modules.pricing.logins.tasks.schedulers.login import RefreshLoginsTask
from src.modules.pricing.sources.domain.enums import (
    SourceCode,
)
from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.sources.domain.models import (
    SourceBubbleModel,
)
from src.modules.pricing.sources.interfaces import ISourceErrorService
from src.modules.pricing.symbols.domain.enums import SymbolCode


class CacheFlusherService:
    def __init__(
        self,
        prices: SourcePriceCache,
        source_bubbles: BubbleSourceCache,
        windows: ISourceWindowService,
        policy: MarketEnginePolicy,
    ) -> None:
        self.prices = prices
        self.source_bubbles = source_bubbles
        self.windows = windows
        self.max_quote_age_seconds = policy.max_quote_age_seconds
        self.irans = IranMarketPriceHelper()
        self.suppliers = SupplierMarketPriceHelper()
        self.worlds = GlobalMarketPriceHelper()

    async def flush_results(
        self,
        cfg: CFGContext,
        quotes: SourceQuote,
    ) -> int:
        """
        Desc: Cache every quote under the symbol it was read for, and every
        premium under its asset.
        Args:
            cfg (CFGContext): What the crawl ran against, holding the ids
                the quotes have to be attributed to.
            quotes (SourceQuote): What the crawl came back with.
        Returns:
            return (int): How many readings were cached.
        """
        source_ids = {source.code: source.id for source in cfg.sources}
        symbol_ids = {symbol.code: symbol.id for symbol in cfg.symbols}
        asset_ids = {asset.code: asset.id for asset in cfg.assets}
        codes = {id: code for code, id in symbol_ids.items()}

        built = [
            *self.irans.build(symbol_ids, source_ids, quotes.irans),
            *self.suppliers.build(symbol_ids, source_ids, quotes.suppliers),
            *self.worlds.build(symbol_ids, source_ids, quotes.globals),
        ]
        readings: dict[SymbolCode, list[PricedSourceModel]] = defaultdict(list)
        for reading in built:
            readings[codes[reading.symbol_id]].append(reading)

        premiums: dict[AssetCode, list[SourceBubbleModel]] = defaultdict(list)
        for bubble in quotes.bubbles:
            source_id = source_ids.get(bubble.code)
            asset_id = asset_ids.get(bubble.asset)
            if source_id is None or asset_id is None:
                continue
            premiums[bubble.asset].append(
                SourceBubbleModel(
                    source_id=source_id,
                    asset_id=asset_id,
                    amount=bubble.amount,
                    priced_at=date_utils.utc_now(),
                )
            )

        if readings:
            current = await self.prices.set_many_if_priced_at_newer(
                readings, max_age_seconds=self.max_quote_age_seconds
            )
            if current:
                await self.windows.update_window(current)
        if premiums:
            await self.source_bubbles.set_many(premiums)
        return sum(len(rows) for rows in readings.values())


class PushedFlusherService:
    def __init__(
        self,
        prices: SourcePriceCache,
        windows: ISourceWindowService,
        policy: MarketEnginePolicy,
    ) -> None:
        self.prices = prices
        self.windows = windows
        self.max_quote_age_seconds = policy.max_quote_age_seconds
        self.suppliers = SupplierMarketPriceHelper()

    async def flush_supplier(
        self,
        source: SourceContext,
        symbols: Mapping[SymbolCode, int],
        quotes: Sequence[SupplierSourceQuote],
    ) -> int:
        """
        Desc: Put what one wholesaler pushed under the line it quoted. It
            writes its own field and no other, so a crawl running at the
            same moment cannot take it back off the board.
        Args:
            source (SourceContext): The source the quotes came from.
            symbols (Mapping[SymbolCode, int]): The id each line has.
            quotes (Sequence[SupplierSourceQuote]): What it sent.
        Returns:
            return (int): How many readings were cached.
        """
        built = self.suppliers.build(
            dict(symbols), {source.code: source.id}, quotes
        )
        codes = {id: code for code, id in symbols.items()}
        readings: dict[SymbolCode, list[PricedSourceModel]] = defaultdict(list)
        for reading in built:
            readings[codes[reading.symbol_id]].append(reading)
        current = await self.prices.set_many_if_priced_at_newer(
            readings, max_age_seconds=self.max_quote_age_seconds
        )
        if current:
            await self.windows.update_window(current)
        return sum(len(rows) for rows in current.values())


class SelectionService:
    def __init__(self, selections: SourceSelectionCache) -> None:
        self.selections = selections

    async def record(
        self,
        symbols: Mapping[int, SymbolCode],
        verdicts: Sequence[PricedSourceModel],
    ) -> int:
        """
        Desc: Store how the calculator judged each reading, on its own key
            so a crawl writing prices can never clobber it.
        Args:
            symbols (Mapping[int, SymbolCode]): Which line every symbol id
                stands for.
            verdicts (Sequence[PricedSourceModel]): The judged readings.
        Returns:
            return (int): How many verdicts were stored.
        """
        by_symbol: dict[SymbolCode, list[SourceSelectionModel]] = defaultdict(
            list
        )
        for row in verdicts:
            code = symbols.get(row.symbol_id)
            if code is None:
                continue
            by_symbol[code].append(
                SourceSelectionModel(
                    source_id=row.source_id,
                    symbol_id=row.symbol_id,
                    is_selected=row.is_selected,
                    reason=row.reason,
                    priced_at=row.priced_at,
                )
            )
        if by_symbol:
            await self.selections.set_many(by_symbol)
        return sum(len(rows) for rows in by_symbol.values())


class PersistFlusherService:
    refused_codes = (401, 403)

    def __init__(self, errors: ISourceErrorService) -> None:
        self.errors = errors

    def _refused(
        self,
        quotes: Sequence[SupplierSourceQuote],
    ) -> list[SourceCode]:
        """
        Desc: Pick out the wholesalers that turned the crawl away because
            its credentials no longer hold.
        Args:
            quotes (Sequence[SupplierSourceQuote]): The failed supplier
                quotes of one crawl.
        Returns:
            return (list[SourceCode]): Their codes, each named once.
        """
        refused = []
        for row in quotes:
            error = row.error
            if error is None or error.http_error is None:
                continue
            if int(error.http_error.status_code) not in self.refused_codes:
                continue
            if row.code not in refused:
                refused.append(row.code)
        return refused

    def _as_info(self, error: ErrorQuote) -> SourceErrorInfo:
        """
        Desc: Turn what a gateway reported into what a source row stores.
        Args:
            error (ErrorQuote): What the fetcher came back with.
        Returns:
            return (SourceErrorInfo): The row payload.
        """
        info = SourceErrorInfo(kind=error.error_type, message=error.message)
        if error.http_error is not None:
            info["status_code"] = int(error.http_error.status_code)
            info["raw_content"] = error.http_error.raw_content
        return info

    @handle_conflicts
    async def flush_errors(
        self,
        cfg: CFGContext,
        quotes: SourceQuote,
    ) -> int:
        """
        Desc: Stamp every source that failed, and clear the error every
        other crawled source carried from the last run.
        Args:
            cfg (CFGContext): What the crawl ran against.
            quotes (SourceQuote): The quotes that came back failed.
        Returns:
            return (int): How many sources were stamped.
        """
        async with transaction():
            source_ids = {source.code: source.id for source in cfg.sources}
            called = {
                *SUPPLIER_FETCHERS,
                *IRAN_FETCHERS,
                *GLOBAL_FETCHERS,
                *BUBBLE_FETCHERS,
            }
            errors: dict[int, SourceErrorInfo | None] = {
                id: None for code, id in source_ids.items() if code in called
            }
            rows = (
                list(quotes.irans)
                + list(quotes.suppliers)
                + list(quotes.globals)
                + list(quotes.bubbles)
            )
            for row in rows:
                source_id = source_ids.get(row.code)
                if source_id is None or row.error is None:
                    continue
                errors[source_id] = self._as_info(row.error)
            if errors:
                await self.errors.apply_errors(errors)
            refused = self._refused(quotes.suppliers)
        if refused:
            await RefreshLoginsTask.enqueue(codes=refused)
        return len(errors)
