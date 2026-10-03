from collections import defaultdict
from typing import Mapping, Sequence

from papilio.core import resources as framework_resources
from papilio.errors.exceptions import NotFoundException

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.app.helpers import (
    Aggregator,
    GlobalMarketCalculator,
    IranMarketCalculator,
    SupplierCalculator,
)
from src.modules.pricing.calculator.domain.context import (
    AssetContext,
    BubbleContext,
    SwitchOrderContext,
)
from src.modules.pricing.calculator.domain.models import (
    AssetBubbleModel,
    AssetPriceModel,
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
from src.modules.pricing.candle.interfaces import IWindowService
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
)
from src.modules.pricing.engine.interfaces import (
    ICacheReaderService,
    ISelectionService,
)
from src.modules.pricing.sources.domain.enums import (
    SelectionReason,
    SourceSwitch,
)
from src.modules.pricing.sources.domain.models import (
    SourceBubbleModel,
)


class BubbleCalculatorService:
    def __init__(
        self,
        bubbles: BubbleReader,
        published: ICacheReaderService,
        cache: BubbleCache,
    ) -> None:
        self.bubbles = bubbles
        self.published = published
        self.cache = cache
        self.aggregator = Aggregator()

    def _settled(
        self,
        bubble: BubbleContext,
        published: Sequence[SourceBubbleModel],
    ) -> AssetBubbleModel | None:
        """
        Desc: Fold every published premium of one asset into a settled one.
        Args:
            bubble (BubbleContext): The bubble being settled, with the rule
                its publishers are folded by.
            published (Sequence[SourceBubbleModel]): What each source
                published for that asset.
        Returns:
            return (AssetBubbleModel | None): The settled premium, or None when
                nobody published one.
        """
        result = None
        if published:
            amount = self.aggregator.pick(
                [row.amount for row in published],
                bubble.agg_type,
            )
            result = AssetBubbleModel(
                asset_id=published[0].asset_id,
                amount=amount,
                priced_at=max(row.priced_at for row in published),
            )
        return result

    async def calculate(self, bubble_id: int) -> int:
        """
        Desc: Settle one bubble out of what its publishers last said.
        Args:
            bubble_id (int): ID of the bubble to settle.
        Returns:
            return (int): The settled premium in rial, signed, and zero
                when nobody published one.
        """
        bubble = await self.bubbles.get_bubble_config(bubble_id)
        if bubble is None:
            raise NotFoundException(
                identifier="id",
                identifier_value=bubble_id,
                message=f"Cannot find Bubble by id with value {bubble_id}",
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Bubble",
            )
        published = await self.published.get_bubbles_by_asset(bubble.code)
        result = self._settled(bubble, published)
        amount = 0
        if result is not None:
            await self.cache.set(bubble.code, result)
            amount = result.amount
        return amount

    async def calculate_all(self) -> int:
        """
        Desc: Settle every bubble out of what its publishers last said.
        Returns:
            return (int): How many bubbles were settled.
        """
        bubbles = await self.bubbles.get_all()
        published = await self.published.get_all_bubbles()
        settled: dict[AssetCode, AssetBubbleModel] = {}
        for bubble in bubbles:
            result = self._settled(bubble, published.get(bubble.code, ()))
            if result is not None:
                settled[bubble.code] = result
        if settled:
            await self.cache.set_many(settled)
        return len(settled)


class CalculatorService:
    excludes = (AssetCode.USD,)

    def __init__(
        self,
        assets: AssetReader,
        symbols: SymbolReader,
        orders: SwitchOrderReader,
        sources: SourceReader,
        readings: ICacheReaderService,
        bubbles: BubbleCache,
        prices: AssetPriceCache,
        windows: IWindowService,
        selection: ISelectionService,
        policy: MarketEnginePolicy,
    ) -> None:
        self.assets = assets
        self.symbols = symbols
        self.orders = orders
        self.sources = sources
        self.readings = readings
        self.bubbles = bubbles
        self.prices = prices
        self.windows = windows
        self.selection = selection
        self.iran = IranMarketCalculator(policy)
        self.supplier = SupplierCalculator(policy)
        self.world = GlobalMarketCalculator(policy)

    def _priced(
        self,
        asset: AssetContext,
        order: Sequence[SwitchOrderContext],
        markets: Mapping[SourceSwitch, Sequence[PricedSourceModel]],
        bubble: AssetBubbleModel | None,
        usd_price: int,
        verdicts: list[PricedSourceModel] | None = None,
    ) -> AssetPriceModel | None:
        """
        Desc: Walk an asset's markets and take the first price it gets.
        Args:
            asset (AssetContext): The asset being priced.
            order (Sequence[SwitchOrderContext]): Its markets, the one
                tried first at the front.
            markets (Mapping[SourceSwitch, Sequence[PricedSourceModel]]):
                Its readings, split by the market they were quoted in.
            bubble (AssetBubbleModel | None): Its settled premium, if any.
            usd_price (int): What one dollar costs, in rial.
        Returns:
            return (AssetPriceModel | None): The asset's price, or None
                when no market of its own could price it.
        """
        result = None
        consulted: set[SourceSwitch] = set()
        for row in order:
            rows = markets.get(row.switch, ())
            consulted.add(row.switch)
            if row.switch is SourceSwitch.IRAN_MARKET:
                result = self.iran.calculate(asset, rows, verdicts)
            elif row.switch is SourceSwitch.SUPPLIER:
                result = self.supplier.calculate(asset, rows, verdicts)
            elif row.switch is SourceSwitch.GLOBAL_MARKET:
                result = self.world.calculate(
                    usd_price, bubble, asset, rows, verdicts
                )
            if result is not None:
                break
        if verdicts is not None:
            for switch, rows in markets.items():
                if switch in consulted:
                    continue
                verdicts.extend(
                    row.model_copy(
                        update={
                            "is_selected": False,
                            "reason": SelectionReason.SWITCH_OFF,
                        }
                    )
                    for row in rows
                )
        return result

    async def calculate(self, asset_id: int) -> int:
        """
        Desc: Price one asset from the first of its markets that answers.
        Args:
            asset_id (int): ID of the asset to price.
        Returns:
            return (int): The asset's price in rial, and zero when no
                market of its own could price it.
        """
        asset = await self.assets.get_asset_config(asset_id)
        if asset is None:
            raise NotFoundException(
                identifier="id",
                identifier_value=asset_id,
                message=f"Cannot find Asset by id with value {asset_id}",
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Asset",
            )
        symbols = await self.symbols.get_symbols_of_asset(asset_id)
        order = await self.orders.get_switch_order(asset_id)
        switches = dict(await self.sources.get_source_switches())
        codes = [symbol.symbol for symbol in symbols]
        readings = await self.readings.get_many_by_symbols(codes)
        bubble = await self.bubbles.get(asset.code)
        dollar = await self.prices.get(AssetCode.USD)
        usd_price = 0 if dollar is None else dollar.price

        markets: dict[SourceSwitch, list[PricedSourceModel]] = defaultdict(
            list
        )
        flatten_readings = [row for rows in readings.values() for row in rows]
        for row in flatten_readings:
            switch = switches.get(row.source_id)
            if switch is not None:
                markets[switch].append(row)

        verdicts: list[PricedSourceModel] = []
        result = self._priced(
            asset, order, markets, bubble, usd_price, verdicts
        )
        await self.selection.record(
            {symbol.id: symbol.symbol for symbol in symbols}, verdicts
        )
        price = 0
        if result is not None:
            await self.prices.set(asset.code, result)
            await self.windows.update_window(asset.code, result)

            price = result.price
        return price

    async def calculate_usd(self) -> int:
        """
        Desc: Price the dollar on its own, the rate a sweep reads world
        parity at.
        Returns:
            return (int): The dollar's price in rial, and zero when no
                market of its own could price it.
        """
        asset_id = await self.assets.get_id_by_code(AssetCode.USD)
        if asset_id is None:
            raise NotFoundException(
                identifier="code",
                identifier_value=AssetCode.USD.value,
                message=(
                    f"Cannot find Asset by code with value "
                    f"{AssetCode.USD.value}"
                ),
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Asset",
            )
        price = await self.calculate(asset_id)
        return price

    async def calculate_all(self) -> int:
        """
        Desc: Price every asset but the dollar, each from the first of its
        markets that answers.
        Returns:
            return (int): How many assets were priced.
        """
        assets = await self.assets.get_all_config(self.excludes)
        symbols = await self.symbols.get_all(self.excludes)
        orders = await self.orders.get_all(self.excludes)
        switches = dict(await self.sources.get_source_switches())
        readings = await self.readings.get_all()
        bubbles = await self.bubbles.get_all()
        dollar = await self.prices.get(AssetCode.USD)
        usd_price = 0 if dollar is None else dollar.price

        ordered: dict[int, list[SwitchOrderContext]] = defaultdict(list)
        for row in orders:
            ordered[row.asset_id].append(row)

        markets: dict[int, dict[SourceSwitch, list[PricedSourceModel]]] = (
            defaultdict(lambda: defaultdict(list))
        )
        symbol_dict = {symbol.id: symbol for symbol in symbols}
        flattend_readings = [row for rows in readings.values() for row in rows]
        for row in flattend_readings:
            symbol = symbol_dict.get(row.symbol_id)
            if symbol is not None:
                switch = switches.get(row.source_id)
                if switch is not None:
                    markets[symbol.asset_id][switch].append(row)

        priced: dict[AssetCode, AssetPriceModel] = {}
        verdicts: list[PricedSourceModel] = []
        for asset in assets:
            result = self._priced(
                asset,
                ordered.get(asset.asset_id, ()),
                markets.get(asset.asset_id, {}),
                bubbles.get(asset.code),
                usd_price,
                verdicts,
            )
            if result is not None:
                priced[asset.code] = result
        await self.selection.record(
            {symbol.id: symbol.symbol for symbol in symbols}, verdicts
        )
        if priced:
            await self.prices.set_many(priced)
            await self.windows.update_windows(priced)

        return len(priced)
