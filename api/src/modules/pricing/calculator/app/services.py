from typing import Mapping, Sequence

from papilio.core import resources as framework_resources
from papilio.errors.exceptions import NotFoundException

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.app.helpers import SymbolConverter
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.calculator.infra.cache import AssetPriceCache
from src.modules.pricing.calculator.infra.readers import (
    AssetReader,
    SymbolReader,
)
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
    PriceModel,
)
from src.modules.pricing.engine.interfaces import ICacheReaderService
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode


class SymbolConverterService:
    natives: Mapping[AssetCode, SymbolCode] = {
        AssetCode.GOLD18: SymbolCode.GOLD18_GRAM,
        AssetCode.SILVER999: SymbolCode.SILVER_GRAM,
        AssetCode.USD: SymbolCode.USD_RIAL,
        AssetCode.USDT: SymbolCode.USDT_RIAL,
    }

    def __init__(
        self,
        assets: AssetReader,
        symbols: SymbolReader,
        prices: AssetPriceCache,
        readings: ICacheReaderService,
    ) -> None:
        self.assets = assets
        self.symbols = symbols
        self.prices = prices
        self.readings = readings
        self.converter = SymbolConverter()

    def _converted(
        self,
        price: int,
        of: SymbolCode,
        to: SymbolCode,
        usd_price: int,
    ) -> int:
        quoted = (
            self.converter.currencies.get(of),
            self.converter.currencies.get(to),
        )
        if CurrencyType.USD in quoted:
            converted = self.converter.convert_with_usd(
                price, of, to, usd_price
            )
        else:
            converted = self.converter.convert(price, of, to)
        return converted

    def _restated(
        self,
        row: PriceModel,
        of: SymbolCode,
        to: SymbolCode,
        usd_price: int,
    ) -> PriceModel:
        buying = self._converted(row.buy_price, of, to, usd_price)
        selling = self._converted(row.sell_price, of, to, usd_price)
        price = self._converted(row.price, of, to, usd_price)
        divisor = price or 1
        buy_spread = price - buying
        sell_spread = selling - price
        restated = PriceModel(
            buy_price=buying,
            sell_price=selling,
            price=price,
            buy_spread=buy_spread,
            sell_spread=sell_spread,
            buy_spread_rate=buy_spread / divisor,
            sell_spread_rate=sell_spread / divisor,
            priced_at=row.priced_at,
            timestamp_kind=row.timestamp_kind,
        )
        return restated

    def _restated_reading(
        self,
        row: PricedSourceModel,
        of: SymbolCode,
        to: SymbolCode,
        usd_price: int,
    ) -> PricedSourceModel:
        restated = self._restated(row, of, to, usd_price)
        reading = PricedSourceModel(
            symbol_id=row.symbol_id,
            source_id=row.source_id,
            currency=self.converter.currencies.get(to, CurrencyType.RIAL),
            is_closed=row.is_closed,
            is_selected=row.is_selected,
            fee=row.fee,
            reason=row.reason,
            buy_price=restated.buy_price,
            sell_price=restated.sell_price,
            price=restated.price,
            buy_spread=restated.buy_spread,
            sell_spread=restated.sell_spread,
            buy_spread_rate=restated.buy_spread_rate,
            sell_spread_rate=restated.sell_spread_rate,
            priced_at=restated.priced_at,
        )
        return reading

    def _asset_not_found(self, asset_id: int) -> NotFoundException:
        return NotFoundException(
            identifier="id",
            identifier_value=asset_id,
            message=f"Cannot find Asset by id with value {asset_id}",
            message_code=framework_resources.NOT_FOUND_ERROR,
            entity="Asset",
        )

    async def _usd_price(self) -> int:
        settled = await self.prices.get(AssetCode.USD)
        usd_price = settled.price if settled is not None else 0
        return usd_price

    async def convert_asset(
        self,
        asset_id: int,
        to_symbol_code: SymbolCode,
    ) -> AssetPriceModel:
        """
        Desc: State what one asset settled at on the symbol asked for.
        Args:
            asset_id (int): ID of the asset that was priced.
            to_symbol_code (SymbolCode): The symbol to state it on.
        Returns:
            return (AssetPriceModel): Its price, on that symbol.
        """
        asset = await self.assets.get_asset_config(asset_id)
        if asset is None:
            raise self._asset_not_found(asset_id)
        settled = await self.prices.get_many([asset.code, AssetCode.USD])
        price = settled.get(asset.code)
        if price is None:
            raise NotFoundException(
                identifier="id",
                identifier_value=asset_id,
                message=f"Asset {asset.code.value} has no price yet",
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Price",
            )
        native = self.natives.get(asset.code)
        if native is None:
            raise NotFoundException(
                identifier="id",
                identifier_value=asset_id,
                message=(
                    f"Asset {asset.code.value} is quoted on no symbol of "
                    f"its own"
                ),
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Symbol",
            )
        usd = settled.get(AssetCode.USD)
        restated = self._restated(
            price,
            native,
            to_symbol_code,
            usd.price if usd is not None else 0,
        )
        converted = AssetPriceModel(
            asset_id=price.asset_id,
            buy_price=restated.buy_price,
            sell_price=restated.sell_price,
            price=restated.price,
            buy_spread=restated.buy_spread,
            sell_spread=restated.sell_spread,
            buy_spread_rate=restated.buy_spread_rate,
            sell_spread_rate=restated.sell_spread_rate,
            priced_at=restated.priced_at,
        )
        return converted

    async def convert_all_sources_of_asset(
        self,
        asset_id: int,
        to_symbol_code: SymbolCode,
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: State what every source of one asset last quoted on the symbol
            asked for, so readings taken on different symbols compare.
        Args:
            asset_id (int): ID of the asset whose sources to read.
            to_symbol_code (SymbolCode): The symbol to state them all on.
        Returns:
            return (Sequence[PricedSourceModel]): The readings, restated.
        """
        symbols = await self.symbols.get_symbols_of_asset(asset_id)
        if not symbols:
            raise self._asset_not_found(asset_id)
        quoted = await self.readings.get_many_by_symbols(
            [row.symbol for row in symbols]
        )
        usd_price = await self._usd_price()
        converted = [
            self._restated_reading(row, symbol, to_symbol_code, usd_price)
            for symbol, rows in quoted.items()
            for row in rows
        ]
        return converted
