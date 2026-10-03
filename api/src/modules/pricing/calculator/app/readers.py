from typing import Mapping, Sequence

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.domain.models import (
    AssetBubbleModel,
    AssetPriceModel,
)
from src.modules.pricing.calculator.infra.cache import (
    AssetPriceCache,
    BubbleCache,
)


class CacheReaderService:
    def __init__(
        self,
        prices: AssetPriceCache,
        bubbles: BubbleCache,
    ) -> None:
        self.prices = prices
        self.bubbles = bubbles

    async def get_price(
        self,
        asset_code: AssetCode,
    ) -> AssetPriceModel | None:
        """
        Desc: Read what one asset was last priced at.
        Args:
            asset_code (AssetCode): The asset to read.
        Returns:
            return (AssetPriceModel | None): Its price, or None when it
                has not been priced yet.
        """
        found = await self.prices.get(asset_code)
        return found

    async def get_bubble_amount(
        self,
        bubble_code: AssetCode,
    ) -> AssetBubbleModel | None:
        """
        Desc: Read one asset's last settled premium.
        Args:
            bubble_code (AssetCode): The asset whose premium to read.
        Returns:
            return (AssetBubbleModel | None): Its premium, or None when none
                has been settled yet.
        """
        found = await self.bubbles.get(bubble_code)
        return found

    async def get_prices(
        self, asset_codes: Sequence[AssetCode]
    ) -> Mapping[AssetCode, AssetPriceModel]:
        """
        Desc: Read the latest prices of the named assets in one call.
        Args:
            asset_codes (Sequence[AssetCode]): Assets to read.
        Returns:
            return (Mapping[AssetCode, AssetPriceModel]): Found prices.
        """
        found = await self.prices.get_many(asset_codes)
        return found

    async def get_all_bubble_amounts(self) -> Sequence[AssetBubbleModel]:
        """
        Desc: Read every premium that has been settled.
        Returns:
            return (Sequence[AssetBubbleModel]): The settled premiums, empty
                when none has been.
        """
        found = await self.bubbles.get_all()
        return list(found.values())

    async def get_all_prices(self) -> Sequence[AssetPriceModel]:
        """
        Desc: Read the price of every asset that has one.
        Returns:
            return (Sequence[AssetPriceModel]): The prices, empty when
                nothing has been priced yet.
        """
        found = await self.prices.get_all()
        return list(found.values())
