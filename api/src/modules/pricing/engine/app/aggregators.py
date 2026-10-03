from typing import Sequence

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.domain.enums import AggregationType
from src.modules.pricing.assets.interfaces import IAssetConfigService
from src.modules.pricing.calculator.app.helpers import (
    AbstractMarketCalculator,
    Aggregator,
)
from src.modules.pricing.engine.domain.models import (
    AggregatedPriceModel,
    AggValueModel,
    PricedSourceModel,
    SymbolAggModel,
)
from src.modules.pricing.engine.interfaces import ICacheReaderService
from src.modules.pricing.sources.domain.models import (
    SourceModel,
    SourceWithPriceModel,
)
from src.modules.pricing.sources.interfaces import ISourceService
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.interfaces import ISymbolService


class AggregatorService:
    def __init__(
        self,
        symbols: ISymbolService,
        configs: IAssetConfigService,
        sources: ISourceService,
        readings: ICacheReaderService,
        policy: MarketEnginePolicy,
    ) -> None:
        self.symbols = symbols
        self.configs = configs
        self.sources = sources
        self.readings = readings
        self.aggregator = Aggregator()
        self.calculator = AbstractMarketCalculator(policy)

    async def agg(self, code: SymbolCode) -> AggregatedPriceModel:
        """
        Desc: Fold what every source last quoted for one line into a single
            price, by the rule the line's own asset is aggregated under, and
            answer with the sources that went into it.
        Args:
            code (SymbolCode): The line to fold.
        Returns:
            return (AggregatedPriceModel): The folded price, the rule it
                was folded by, and every source behind it.
        """
        symbol = await self.symbols.get_by_code(code)
        config = await self.configs.get_by_asset_id(symbol.asset_id)
        readings = await self.readings.get_by_symbol(code)
        judged = self.calculator._judged(readings)
        taken = [row for row in judged if row.is_selected]
        sources = await self.sources.get_by_ids(
            [row.source_id for row in judged]
        )
        result = 0
        if taken:
            result = self.aggregator.pick(
                [row.price for row in taken], config.agg_type
            )
        return AggregatedPriceModel(
            symbol_id=symbol.id,
            result=result,
            agg_type=config.agg_type,
            sources=self._joined(sources, judged),
        )

    async def stats(self, code: SymbolCode) -> SymbolAggModel:
        """
        Desc: Fold what every source last quoted for one line once per rule
            there is, so what each of them would price it at can be read
            beside the rule the line is actually folded by.
        Args:
            code (SymbolCode): The line to fold.
        Returns:
            return (SymbolAggModel): Every source behind the line, what
                each rule prices it at, and the rule in force.
        """
        symbol = await self.symbols.get_by_code(code)
        config = await self.configs.get_by_asset_id(symbol.asset_id)
        readings = await self.readings.get_by_symbol(code)
        judged = self.calculator._judged(readings)
        sources = await self.sources.get_by_ids(
            [row.source_id for row in judged]
        )
        prices = [row.price for row in judged if row.is_selected]
        aggs = [
            AggValueModel(
                agg_type=agg_type,
                result=(
                    self.aggregator.pick(prices, agg_type) if prices else 0
                ),
            )
            for agg_type in AggregationType
        ]
        return SymbolAggModel(
            symbol_id=symbol.id,
            agg_type=config.agg_type,
            aggs=aggs,
            sources=self._joined(sources, judged),
        )

    def _joined(
        self,
        sources: Sequence[SourceModel],
        readings: Sequence[PricedSourceModel],
    ) -> list[SourceWithPriceModel]:
        priced = {row.source_id: row for row in readings}
        joined = []
        for source in sources:
            reading = priced.get(source.id)
            if reading is None:
                continue
            joined.append(
                SourceWithPriceModel(
                    **source.model_dump(),
                    **reading.model_dump(
                        exclude={"symbol_id", "source_id", "fee"}
                    ),
                )
            )
        return joined
