from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import (
    RedisScheduler,
)

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.infra.readers import AssetReader
from src.modules.pricing.calculator.interfaces import ICalculatorService


class CalculateUsdTask(RedisScheduler):
    def __init__(self, service: ICalculatorService) -> None:
        self.service = service

    async def run(self) -> int:
        price = await self.service.calculate_usd()
        logger.info("dollar priced at %s", price)
        return price


class CalculateAssetTask(RedisScheduler):
    def __init__(self, service: ICalculatorService) -> None:
        self.service = service

    async def run(self, asset_id: int) -> int:
        price = await self.service.calculate(asset_id)
        logger.info("asset %s priced at %s", asset_id, price)
        return price


class RepriceAssetTask(RedisScheduler):
    def __init__(
        self, assets: AssetReader, service: ICalculatorService
    ) -> None:
        self.assets = assets
        self.service = service

    async def run(self, code: AssetCode) -> int:
        asset_id = await self.assets.get_id_by_code(code)
        price = 0
        if asset_id is None:
            logger.warning("no asset carries the code %s", code)
        else:
            price = await self.service.calculate(asset_id)
            logger.info("asset %s repriced at %s", code, price)
        return price
