from collections.abc import Awaitable
from typing import Mapping, Protocol, Sequence

from papilio.errors.exceptions import ValidationException
from papilio.schemas.results import BatchResultType

from src.modules.pricing.assets.domain.dtos import (
    AssetConfigUpdate,
    AssetCreate,
    AssetSwitchBatchCreate,
    AssetSwitchBatchDelete,
    AssetSwitchBatchUpdate,
    AssetSwitchCreate,
    AssetSwitchPriorityUpdate,
    AssetSwitchUpdate,
    AssetUpdate,
)
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.domain.models import (
    AssetConfigModel,
    AssetModel,
    AssetPriceSummary,
    AssetsMetaModel,
    AssetSwitchModel,
    AssetWithConfigModel,
)
from src.modules.pricing.assets.domain.results import AssetSourcePriceResult


class IAssetPriceQuery(Protocol):
    def get_by_code(
        self, asset_code: AssetCode
    ) -> Awaitable[AssetPriceSummary]: ...

    def get_all(self) -> Awaitable[Sequence[AssetPriceSummary]]: ...


class IAssetConfigService(Protocol):
    def create_default(
        self,
        asset_id: int,
        code: AssetCode,
    ) -> Awaitable[AssetConfigModel]: ...

    def create_defaults(
        self, assets: Mapping[int, AssetCode]
    ) -> Awaitable[Sequence[AssetConfigModel]]: ...

    def update(
        self,
        asset_id: int,
        data: AssetConfigUpdate,
    ) -> Awaitable[AssetConfigModel]: ...

    def get_by_asset_id(
        self, asset_id: int
    ) -> Awaitable[AssetConfigModel]: ...

    def get_all(self) -> Awaitable[Sequence[AssetConfigModel]]: ...


class IAssetSwitchService(Protocol):
    def create(
        self,
        asset_id: int,
        data: AssetSwitchCreate,
    ) -> Awaitable[AssetSwitchModel]: ...

    def batch_create(
        self,
        asset_id: int,
        data: AssetSwitchBatchCreate,
    ) -> Awaitable[Sequence[AssetSwitchModel]]: ...

    def batch_create_many(
        self, assets: Mapping[int, AssetSwitchBatchCreate]
    ) -> Awaitable[Sequence[AssetSwitchModel]]: ...

    def update(
        self,
        asset_id: int,
        id: int,
        data: AssetSwitchUpdate,
    ) -> Awaitable[AssetSwitchModel]: ...

    def batch_update(
        self,
        asset_id: int,
        data: AssetSwitchBatchUpdate,
    ) -> Awaitable[Sequence[AssetSwitchModel]]: ...

    def set_priority(
        self,
        asset_id: int,
        data: AssetSwitchPriorityUpdate,
    ) -> Awaitable[Sequence[AssetSwitchModel]]: ...

    def remove(
        self, asset_id: int, id: int
    ) -> Awaitable[AssetSwitchModel]: ...

    def batch_remove(
        self,
        asset_id: int,
        data: AssetSwitchBatchDelete,
    ) -> Awaitable[BatchResultType[AssetSwitchModel, ValidationException]]: ...

    def get_by_asset_id(
        self,
        asset_id: int,
    ) -> Awaitable[Sequence[AssetSwitchModel]]: ...


class IAssetService(Protocol):
    def create(self, data: AssetCreate) -> Awaitable[AssetModel]: ...

    def update(self, id: int, data: AssetUpdate) -> Awaitable[AssetModel]: ...

    def get_by_id(self, id: int) -> Awaitable[AssetModel]: ...

    def get_by_ids(
        self, ids: list[int]
    ) -> Awaitable[Sequence[AssetModel]]: ...

    def get_all(self) -> Awaitable[Sequence[AssetModel]]: ...

    def get_by_code(self, code: AssetCode) -> Awaitable[AssetModel]: ...

    def remove(self, id: int) -> Awaitable[AssetModel]: ...

    def get_batch(
        self,
        ids: list[int],
    ) -> Awaitable[BatchResultType[AssetModel, ValidationException]]: ...


class IAssetMetaService(Protocol):
    def build(
        self, asset_ids: Sequence[int]
    ) -> Awaitable[AssetsMetaModel]: ...


class IAssetSourcePriceService(Protocol):
    def get_by_asset_id(
        self, asset_id: int
    ) -> Awaitable[AssetSourcePriceResult]: ...


class ICreateAsset(Protocol):
    def execute(self, data: AssetCreate) -> Awaitable[AssetModel]: ...


class IUpdateAssetConfig(Protocol):
    def execute(
        self, asset_id: int, data: AssetConfigUpdate
    ) -> Awaitable[AssetConfigModel]: ...


class IGetAssetsWithConfig(Protocol):
    def execute(self) -> Awaitable[Sequence[AssetWithConfigModel]]: ...
