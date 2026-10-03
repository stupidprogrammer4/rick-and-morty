import statistics
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Mapping, Sequence

from papilio.core import resources as framework_resources
from papilio.errors.exceptions import ValidationException
from papilio.utils.currency import MAZANE_FACTOR, TROY_OUNCE_GRAMS

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.calculator.domain.context import AssetContext
from src.modules.pricing.calculator.domain.models import (
    AssetBubbleModel,
    AssetPriceModel,
)
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
)
from src.modules.pricing.sources.domain.enums import SelectionReason
from src.modules.pricing.symbols.domain.enums import (
    CurrencyType,
    SymbolCode,
)
from src.tools.currency import round_rial


class Aggregator:
    def _quantile(
        self,
        ordered: Sequence[int],
        share: float,
    ) -> float:
        position = (len(ordered) - 1) * share
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        step = ordered[high] - ordered[low]
        value = ordered[low] + step * (position - low)
        return value

    def pick(
        self,
        values: Sequence[int],
        agg: AggregationType,
    ) -> int:
        """
        Desc: Fold several readings into one price by the given rule.
        Args:
            values (Sequence[int]): Prices to fold, in rial.
            agg (AggregationType): Rule the prices are folded by.
        Returns:
            return (int): The folded price, in rial.
        """
        rule = AggregationType(agg)
        ordered = sorted(values)
        picked: float = statistics.median(ordered)
        if rule is AggregationType.MEAN:
            picked = statistics.fmean(ordered)
        elif rule is AggregationType.MIN:
            picked = ordered[0]
        elif rule is AggregationType.MAX:
            picked = ordered[-1]
        elif rule is AggregationType.FIRST_QUARTILE:
            picked = self._quantile(ordered, 0.25)
        elif rule is AggregationType.THIRD_QUARTILE:
            picked = self._quantile(ordered, 0.75)
        return round_rial(picked)


class AbstractMarketCalculator(ABC):
    def __init__(self, policy: MarketEnginePolicy) -> None:
        self.outlier_rate = policy.outlier_rate
        self.min_outlier_sample = policy.min_outlier_sample
        self.aggregator = Aggregator()

    def _restated(
        self,
        reading: PricedSourceModel,
        buying: int,
        selling: int,
    ) -> PricedSourceModel:
        restated = reading.model_copy(
            update={
                "currency": CurrencyType.RIAL,
                "buy_price": buying,
                "sell_price": selling,
                "price": round_rial((buying + selling) / 2),
            }
        )
        return restated

    def _judged(
        self,
        readings: Sequence[PricedSourceModel],
    ) -> list[PricedSourceModel]:
        """
        Desc: Mark every reading as taken, as an outlier, or as a market
            that is shut, dropping none, so the panel can show what was
            passed over and why. A shut market quotes zero and is left out
            of the median it would otherwise drag down.
        Args:
            readings (Sequence[PricedSourceModel]): One market's readings.
        Returns:
            return (list[PricedSourceModel]): The same readings, judged.
        """
        quoting = [row for row in readings if not row.is_closed]
        gap = None
        if len(quoting) >= self.min_outlier_sample:
            middle = statistics.median([row.price for row in quoting])
            if middle:
                gap = (middle, middle * self.outlier_rate)
        judged = []
        for row in readings:
            reason = None
            if row.is_closed:
                taken = False
                reason = SelectionReason.CLOSED_MARKET
            else:
                taken = gap is None or abs(row.price - gap[0]) <= gap[1]
                if not taken:
                    reason = SelectionReason.OUTLIER
            judged.append(
                row.model_copy(update={"is_selected": taken, "reason": reason})
            )
        return judged

    def _fold(
        self,
        asset: AssetContext,
        readings: Sequence[PricedSourceModel],
        verdicts: list[PricedSourceModel] | None = None,
    ) -> AssetPriceModel | None:
        result = None
        judged = self._judged(readings)
        if verdicts is not None:
            verdicts.extend(judged)
        kept = [row for row in judged if row.is_selected]
        if kept:
            agg = asset.agg_type
            buying = self.aggregator.pick([row.buy_price for row in kept], agg)
            selling = self.aggregator.pick(
                [row.sell_price for row in kept], agg
            )
            price = round_rial((buying + selling) / 2)
            divisor = price or 1
            buy_spread = price - buying
            sell_spread = selling - price
            result = AssetPriceModel(
                asset_id=asset.asset_id,
                buy_price=buying,
                sell_price=selling,
                price=price,
                buy_spread=buy_spread,
                sell_spread=sell_spread,
                buy_spread_rate=buy_spread / divisor,
                sell_spread_rate=sell_spread / divisor,
                priced_at=min(row.priced_at for row in kept),
                timestamp_kind="source"
                if all(row.timestamp_kind == "source" for row in kept)
                else "fetched",
            )
        return result


class AbstractLocalMarketCalculator(AbstractMarketCalculator):
    @abstractmethod
    def calculate(
        self,
        asset: AssetContext,
        sources: Sequence[PricedSourceModel],
        verdicts: list[PricedSourceModel] | None = None,
    ) -> AssetPriceModel | None:
        """
        Desc: Price one asset from the readings of a local market.
        Args:
            asset (AssetContext): Asset being priced and its rule.
            sources (Sequence[PricedSourceModel]): Readings of its sources.
            verdicts (list[PricedSourceModel] | None): Sink for judged rows.
        Returns:
            return (AssetPriceModel | None): The price, or None if unpriced.
        """
        ...

    def calculate_all(
        self,
        assets: Sequence[AssetContext],
        sources: Mapping[int, Sequence[PricedSourceModel]],
    ) -> Sequence[AssetPriceModel]:
        """
        Desc: Price every asset it is given, dropping the unpriced ones.
        Args:
            assets (Sequence[AssetContext]): Assets to price.
            sources (Mapping[int, Sequence[PricedSourceModel]]): Readings.
        Returns:
            return (Sequence[AssetPriceModel]): The prices that settled.
        """
        results = []
        for asset in assets:
            result = self.calculate(asset, sources.get(asset.asset_id, ()))
            if result is not None:
                results.append(result)
        return results


class IranMarketCalculator(AbstractLocalMarketCalculator):
    def calculate(
        self,
        asset: AssetContext,
        sources: Sequence[PricedSourceModel],
        verdicts: list[PricedSourceModel] | None = None,
    ) -> AssetPriceModel | None:
        """
        Desc: Price one asset from the rial readings of its sources.
        Args:
            asset (AssetContext): Asset being priced and its rule.
            sources (Sequence[PricedSourceModel]): Readings of its sources.
            verdicts (list[PricedSourceModel] | None): Sink for judged rows.
        Returns:
            return (AssetPriceModel | None): The price, or None if unpriced.
        """
        readings = [
            row for row in sources if row.currency is CurrencyType.RIAL
        ]
        result = self._fold(asset, readings, verdicts)
        return result


class SupplierCalculator(AbstractLocalMarketCalculator):
    def calculate(
        self,
        asset: AssetContext,
        sources: Sequence[PricedSourceModel],
        verdicts: list[PricedSourceModel] | None = None,
    ) -> AssetPriceModel | None:
        """
        Desc: Price one asset from mazaneh readings restated per gram.
        Args:
            asset (AssetContext): Asset being priced and its rule.
            sources (Sequence[PricedSourceModel]): Readings of its sources.
            verdicts (list[PricedSourceModel] | None): Sink for judged rows.
        Returns:
            return (AssetPriceModel | None): The price, or None if unpriced.
        """
        readings = [
            self._restated(
                row,
                round_rial(Decimal(row.buy_price) / MAZANE_FACTOR),
                round_rial(Decimal(row.sell_price) / MAZANE_FACTOR),
            )
            for row in sources
            if row.currency is CurrencyType.RIAL
        ]
        result = self._fold(asset, readings, verdicts)
        return result


class GlobalMarketCalculator(AbstractMarketCalculator):
    purities: Mapping[AssetCode, Decimal] = {
        AssetCode.GOLD18: Decimal("0.750"),
        AssetCode.SILVER999: Decimal("0.999"),
    }

    def _per_gram(
        self,
        cents: int,
        purity: Decimal,
        usd_price: int,
    ) -> int:
        dollars = Decimal(cents) / 100 / TROY_OUNCE_GRAMS * purity
        rial = round_rial(dollars * usd_price)
        return rial

    def calculate(
        self,
        usd_price: int,
        bubble: AssetBubbleModel | None,
        asset: AssetContext,
        sources: Sequence[PricedSourceModel],
        verdicts: list[PricedSourceModel] | None = None,
    ) -> AssetPriceModel | None:
        """
        Desc: Price one asset from foreign readings and the dollar.
        Args:
            usd_price (int): What a dollar settled at, in rial.
            bubble (AssetBubbleModel | None): Premium to add, if any.
            asset (AssetContext): Asset being priced and its rule.
            sources (Sequence[PricedSourceModel]): Readings of its sources.
            verdicts (list[PricedSourceModel] | None): Sink for judged rows.
        Returns:
            return (AssetPriceModel | None): The price, or None if unpriced.
        """
        result = None
        purity = self.purities.get(asset.code)
        if purity is not None and usd_price > 0:
            premium = bubble.amount if bubble is not None else 0
            readings = [
                self._restated(
                    row,
                    self._per_gram(row.buy_price, purity, usd_price) + premium,
                    self._per_gram(row.sell_price, purity, usd_price)
                    + premium,
                )
                for row in sources
                if row.currency is CurrencyType.USD
            ]
            result = self._fold(asset, readings, verdicts)
        return result

    def calculate_all(
        self,
        usd_price: int,
        bubbles: Mapping[int, AssetBubbleModel],
        assets: Sequence[AssetContext],
        sources: Mapping[int, Sequence[PricedSourceModel]],
    ) -> Sequence[AssetPriceModel]:
        """
        Desc: Price every asset from foreign readings and the dollar.
        Args:
            usd_price (int): What a dollar settled at, in rial.
            bubbles (Mapping[int, AssetBubbleModel]): Premium per asset.
            assets (Sequence[AssetContext]): Assets to price.
            sources (Mapping[int, Sequence[PricedSourceModel]]): Readings.
        Returns:
            return (Sequence[AssetPriceModel]): The prices that settled.
        """
        results = []
        for asset in assets:
            result = self.calculate(
                usd_price,
                bubbles.get(asset.asset_id),
                asset,
                sources.get(asset.asset_id, ()),
            )
            if result is not None:
                results.append(result)
        return results


class SymbolConverter:
    pure_grams: Mapping[SymbolCode, Decimal] = {
        SymbolCode.GOLD18_GRAM: Decimal("0.750"),
        SymbolCode.GOLD18_MAZANE: MAZANE_FACTOR * Decimal("0.750"),
        SymbolCode.XAU_OUNCE: TROY_OUNCE_GRAMS,
        SymbolCode.SILVER_GRAM: Decimal("0.999"),
        SymbolCode.XAG_OUNCE: TROY_OUNCE_GRAMS,
    }
    currencies: Mapping[SymbolCode, CurrencyType] = {
        SymbolCode.GOLD18_GRAM: CurrencyType.RIAL,
        SymbolCode.GOLD18_MAZANE: CurrencyType.RIAL,
        SymbolCode.XAU_OUNCE: CurrencyType.USD,
        SymbolCode.SILVER_GRAM: CurrencyType.RIAL,
        SymbolCode.XAG_OUNCE: CurrencyType.USD,
        SymbolCode.USD_RIAL: CurrencyType.RIAL,
    }
    metals: Mapping[SymbolCode, AssetCode] = {
        SymbolCode.GOLD18_GRAM: AssetCode.GOLD18,
        SymbolCode.GOLD18_MAZANE: AssetCode.GOLD18,
        SymbolCode.XAU_OUNCE: AssetCode.GOLD18,
        SymbolCode.SILVER_GRAM: AssetCode.SILVER999,
        SymbolCode.XAG_OUNCE: AssetCode.SILVER999,
    }

    def _grams_of(self, symbol: SymbolCode) -> Decimal:
        grams = self.pure_grams.get(symbol)
        if grams is None:
            raise ValidationException(
                message=f"{symbol.value} quotes no weight of gold",
                message_code=framework_resources.INVALID_INPUT,
                loc=["query", "symbol_code"],
                input=symbol.value,
            )
        return grams

    def _check_metal(self, of: SymbolCode, to: SymbolCode) -> None:
        quoted = self.metals.get(of), self.metals.get(to)
        if None not in quoted and quoted[0] != quoted[1]:
            raise ValidationException(
                message=(f"{of.value} and {to.value} weigh different metals"),
                message_code=framework_resources.INVALID_INPUT,
                loc=["query", "symbol_code"],
                input=to.value,
            )

    def _check_rial(self, of: SymbolCode, to: SymbolCode) -> None:
        quoted = self.currencies.get(of), self.currencies.get(to)
        if CurrencyType.USD in quoted:
            raise ValidationException(
                message=f"{of.value} to {to.value} needs a dollar price",
                message_code=framework_resources.INVALID_INPUT,
                loc=["query", "symbol_code"],
                input=to.value,
            )

    def _check_usd(self, usd_price: int) -> None:
        if usd_price <= 0:
            raise ValidationException(
                message="A dollar price is needed and none has settled",
                message_code=framework_resources.INVALID_INPUT,
                loc=["query", "symbol_code"],
                input=usd_price,
            )

    def convert(
        self,
        price: int,
        of: SymbolCode,
        to: SymbolCode,
    ) -> int:
        """
        Desc: Restate a rial price read on one symbol as a rial price on
            another, through the weight of pure gold each of them quotes.
        Args:
            price (int): The price as read, in rial.
            of (SymbolCode): The symbol it was read on.
            to (SymbolCode): The symbol to restate it on.
        Returns:
            return (int): The restated price, in rial.
        """
        converted = (
            round_rial(price)
            if self.currencies.get(to) is CurrencyType.RIAL
            else price
        )
        if of is not to:
            self._check_metal(of, to)
            self._check_rial(of, to)
            per_gram = Decimal(price) / self._grams_of(of)
            converted = round_rial(per_gram * self._grams_of(to))
        return converted

    def convert_with_usd(
        self,
        price: int,
        of: SymbolCode,
        to: SymbolCode,
        usd_price: int,
    ) -> int:
        """
        Desc: Restate a price across the dollar, so a symbol quoted in cent
            and a symbol quoted in rial can be read as one another.
        Args:
            price (int): The price as read, cent or rial by its symbol.
            of (SymbolCode): The symbol it was read on.
            to (SymbolCode): The symbol to restate it on.
            usd_price (int): What a dollar settled at, in rial.
        Returns:
            return (int): The restated price, cent or rial by `to`.
        """
        converted = (
            round_rial(price)
            if self.currencies.get(to) is CurrencyType.RIAL
            else price
        )
        if of is not to:
            self._check_metal(of, to)
            self._check_usd(usd_price)
            rial = Decimal(price)
            if self.currencies.get(of) is CurrencyType.USD:
                rial = Decimal(price) / 100 * Decimal(usd_price)
            per_gram = rial / self._grams_of(of)
            unit = per_gram * self._grams_of(to)
            converted = round_rial(unit)
            if self.currencies.get(to) is CurrencyType.USD:
                converted = round(unit / Decimal(usd_price) * 100)
        return converted
