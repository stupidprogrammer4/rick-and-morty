from dishka import Provider, Scope, alias, provide

from src.modules.pricing.assets.app.commands import (
    CreateAsset,
    UpdateAssetConfig,
)
from src.modules.pricing.assets.app.queries import (
    AssetPriceQuery,
    GetAssetsWithConfig,
)
from src.modules.pricing.assets.app.services import (
    AssetConfigService,
    AssetMetaService,
    AssetService,
    AssetSourcePriceService,
    AssetSwitchService,
)
from src.modules.pricing.assets.infra.mysql import (
    AssetConfigRepository,
    AssetRepository,
    AssetSwitchRepository,
)
from src.modules.pricing.assets.infra.readers import AssetReader
from src.modules.pricing.assets.interfaces import (
    IAssetConfigService,
    IAssetMetaService,
    IAssetPriceQuery,
    IAssetService,
    IAssetSourcePriceService,
    IAssetSwitchService,
    ICreateAsset,
    IGetAssetsWithConfig,
    IUpdateAssetConfig,
)


class AssetProvider(Provider):
    scope = Scope.REQUEST

    asset_repo = provide(AssetRepository)
    asset_config_repo = provide(AssetConfigRepository)
    asset_switch_repo = provide(AssetSwitchRepository)
    asset_config_service = provide(
        AssetConfigService, provides=IAssetConfigService
    )
    asset_switch_service = provide(
        AssetSwitchService, provides=IAssetSwitchService
    )
    asset_service = provide(AssetService, provides=IAssetService)
    asset_meta_service = provide(AssetMetaService, provides=IAssetMetaService)
    asset_source_price_service = provide(
        AssetSourcePriceService, provides=IAssetSourcePriceService
    )

    reader = provide(AssetReader)
    prices = provide(AssetPriceQuery, provides=IAssetPriceQuery)
    create_asset = provide(CreateAsset)
    update_config = provide(UpdateAssetConfig)
    get_with_config = provide(GetAssetsWithConfig)

    create_asset_contract = alias(CreateAsset, provides=ICreateAsset)

    get_assets_with_config_contract = alias(
        GetAssetsWithConfig, provides=IGetAssetsWithConfig
    )

    update_asset_config_contract = alias(
        UpdateAssetConfig, provides=IUpdateAssetConfig
    )
