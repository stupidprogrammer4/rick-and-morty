from typing import Sequence

from papilio.tools.checks import Checks

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.domain.models import (
    AssetPriceSummary,
    AssetWithConfigModel,
)
from src.modules.pricing.assets.infra.readers import AssetReader
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.calculator.interfaces import ICacheReaderService


class AssetPriceQuery(Checks[AssetPriceModel]):
    entity = "Price"

    def __init__(self, prices: ICacheReaderService) -> None:
        self.prices = prices

    async def get_by_code(self, asset_code: AssetCode) -> AssetPriceSummary:
        found = await self.prices.get_price(asset_code)
        price = self._check_for_existence("code", asset_code, found)
        return AssetPriceSummary(asset_code=asset_code, price=price.price)

    async def get_all(self) -> Sequence[AssetPriceSummary]:
        prices = await self.prices.get_prices(list(AssetCode))
        return [
            AssetPriceSummary(asset_code=code, price=price.price)
            for code, price in prices.items()
        ]


class GetAssetsWithConfig:
    def __init__(self, reader: AssetReader) -> None:
        self.reader = reader

    async def execute(self) -> Sequence[AssetWithConfigModel]:
        assets = await self.reader.get_all_with_config()
        return assets
