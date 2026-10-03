from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional

from src.modules.pricing.assets.domain.dtos import (
    AssetConfigUpdate,
    AssetCreate,
)
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.domain.models import (
    AssetConfigModel,
    AssetModel,
)
from src.modules.pricing.assets.interfaces import (
    IAssetConfigService,
    IAssetService,
)
from src.modules.pricing.calculator.interfaces import ISchedulerService


class CreateAsset:
    def __init__(
        self, assets: IAssetService, configs: IAssetConfigService
    ) -> None:
        self.assets = assets
        self.configs = configs

    @handle_conflicts
    @transactional
    async def execute(self, data: AssetCreate) -> AssetModel:
        """Create the asset and its default config atomically."""
        asset = await self.assets.create(data)
        await self.configs.create_default(asset.id, data.code)
        return asset


class UpdateAssetConfig:
    def __init__(
        self,
        assets: IAssetService,
        configs: IAssetConfigService,
        scheduler: ISchedulerService,
    ) -> None:
        self.assets = assets
        self.configs = configs
        self.scheduler = scheduler

    @handle_conflicts
    @transactional
    async def execute(
        self, asset_id: int, data: AssetConfigUpdate
    ) -> AssetConfigModel:
        """Update config and synchronize its schedule when requested."""
        config = await self.configs.update(asset_id, data)
        if data.scheduler_on is not None or data.scheduler_seconds is not None:
            asset = await self.assets.get_by_id(asset_id)
            if asset.code != AssetCode.USD:
                await self.scheduler.sync(
                    asset_id, config.scheduler_on, config.scheduler_seconds
                )
        return config
