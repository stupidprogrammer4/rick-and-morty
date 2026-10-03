from typing import Sequence

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.engine.domain.context import CFGContext
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
    SourceSelectionModel,
)
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
from src.modules.pricing.sources.domain.enums import (
    SourceUpdateType,
)
from src.modules.pricing.sources.domain.models import (
    SourceBubbleModel,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode


class CFGReaderService:
    update_types = (SourceUpdateType.SCHEDULER,)
    is_active = True

    def __init__(
        self,
        assets: AssetReader,
        symbols: SymbolReader,
        sources: SourceReader,
    ) -> None:
        self.assets = assets
        self.symbols = symbols
        self.sources = sources

    async def read_context(self) -> CFGContext:
        """
        Desc: Read what a crawl needs: every source, and the ids a quoted
        code maps to.
        Returns:
            return (CFGContext): The sources to call, and the symbols and
                assets to attribute their quotes to.
        """
        sources = await self.sources.read_all(
            self.update_types, self.is_active
        )
        symbols = await self.symbols.read_refs()
        assets = await self.assets.read_refs()
        context = CFGContext(sources=sources, symbols=symbols, assets=assets)
        return context


class CacheReaderService:
    def __init__(
        self,
        prices: SourcePriceCache,
        selections: SourceSelectionCache,
        source_bubbles: BubbleSourceCache,
    ) -> None:
        self.prices = prices
        self.selections = selections
        self.source_bubbles = source_bubbles

    def _merged(
        self,
        readings: Sequence[PricedSourceModel],
        verdicts: Sequence[SourceSelectionModel],
    ) -> list[PricedSourceModel]:
        """
        Desc: Stamp each reading with how the calculator judged it. The
            verdict is the calculator's to decide and this only carries it
            through, so a reading keeps the last one passed on it.
        Args:
            readings (Sequence[PricedSourceModel]): What the crawl cached.
            verdicts (Sequence[SourceSelectionModel]): What the
                calculator last decided.
        Returns:
            return (list[PricedSourceModel]): The readings, judged.
        """
        judged = {(row.source_id, row.symbol_id): row for row in verdicts}
        merged = []
        for row in readings:
            verdict = judged.get((row.source_id, row.symbol_id))
            if verdict is not None:
                row = row.model_copy(
                    update={
                        "is_selected": verdict.is_selected,
                        "reason": verdict.reason,
                    }
                )
            merged.append(row)
        return merged

    async def get_by_symbol(
        self,
        symbol: SymbolCode,
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: Read what every source last quoted for one line, and how the
            calculator judged each quote.
        Args:
            symbol (SymbolCode): The line to read.
        Returns:
            return (Sequence[PricedSourceModel]): The readings, empty when
                no crawl has cached that line yet.
        """
        readings = await self.prices.get(symbol)
        if not readings:
            return []
        verdicts = await self.selections.get(symbol)
        return self._merged(readings, verdicts)

    async def get_many_by_symbols(
        self,
        symbols: Sequence[SymbolCode],
    ) -> dict[SymbolCode, Sequence[PricedSourceModel]]:
        """
        Desc: Read what every source last quoted for several lines, and
            how the calculator judged each quote.
        Args:
            symbols (Sequence[SymbolCode]): The lines to read.
        Returns:
            return (dict[SymbolCode, Sequence[PricedSourceModel]]): The
                readings of each line that has any.
        """
        readings = await self.prices.get_many(symbols)
        verdicts = await self.selections.get_many(list(readings))
        return {
            code: self._merged(rows, verdicts.get(code, []))
            for code, rows in readings.items()
        }

    async def get_all(
        self,
    ) -> dict[SymbolCode, Sequence[PricedSourceModel]]:
        """
        Desc: Read the whole board the last crawl left behind, and how the
            calculator judged it.
        Returns:
            return (dict[SymbolCode, Sequence[PricedSourceModel]]): Every
                line that has readings.
        """
        readings = await self.prices.get_all()
        verdicts = await self.selections.get_all()
        return {
            code: self._merged(rows, verdicts.get(code, []))
            for code, rows in readings.items()
        }

    async def get_by_source_id(
        self,
        source_id: int,
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: Read everything one source last quoted, on whatever lines it
            quotes, and how the calculator judged each.
        Args:
            source_id (int): The source to read.
        Returns:
            return (Sequence[PricedSourceModel]): Its readings, empty when
                it has quoted nothing.
        """
        readings = await self.prices.get_by_id(source_id)
        if not readings:
            return []
        verdicts = await self.selections.get_by_id(source_id)
        return self._merged(readings, verdicts)

    async def get_by_source_ids(
        self,
        source_ids: Sequence[int],
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: Read everything several sources last quoted, reaching only
            for their own fields rather than the whole board.
        Args:
            source_ids (Sequence[int]): The sources to read.
        Returns:
            return (Sequence[PricedSourceModel]): Their readings.
        """
        readings = await self.prices.get_by_ids(source_ids)
        if not readings:
            return []
        verdicts = await self.selections.get_by_ids(source_ids)
        return self._merged(readings, verdicts)

    async def get_bubbles_by_asset(
        self,
        code: AssetCode,
    ) -> Sequence[SourceBubbleModel]:
        """
        Desc: Read what every source last published as one asset's premium.
        Args:
            code (AssetCode): The asset to read.
        Returns:
            return (Sequence[SourceBubbleModel]): The premiums, empty when
                no crawl has cached one for that asset yet.
        """
        premiums = await self.source_bubbles.get(code)
        return premiums or []

    async def get_all_bubbles(
        self,
    ) -> dict[AssetCode, Sequence[SourceBubbleModel]]:
        """
        Desc: Read every premium the last crawl left behind.
        Returns:
            return (dict[AssetCode, Sequence[SourceBubbleModel]]): Every
                asset a source published a premium for.
        """
        premiums = await self.source_bubbles.get_all()
        return {code: rows for code, rows in premiums.items()}
