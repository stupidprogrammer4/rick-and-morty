from typing import Mapping, Sequence

from papilio.errors.exceptions import ValidationException
from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional
from papilio.schemas.results import BatchResultType
from papilio.tools.checks import Checks, IDChecks

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.config import resources
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
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.assets.domain.models import (
    AssetConfigModel,
    AssetMetaModel,
    AssetModel,
    AssetsMetaModel,
    AssetSwitchModel,
)
from src.modules.pricing.assets.domain.results import AssetSourcePriceResult
from src.modules.pricing.assets.infra.mysql import (
    AssetConfigRepository,
    AssetRepository,
    AssetSwitchRepository,
)
from src.modules.pricing.assets.interfaces import (
    IAssetService,
)
from src.modules.pricing.engine.interfaces import (
    ICacheReaderService as ISourceCacheReaderService,
)
from src.modules.pricing.sources.domain.enums import SourceSwitch
from src.modules.pricing.sources.domain.models import AdminSourcePriceModel
from src.modules.pricing.sources.interfaces import ISourceMetaService
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.interfaces import ISymbolService


class AssetConfigService(Checks[AssetConfigModel]):
    entity = "AssetConfig"

    def __init__(
        self,
        repo: AssetConfigRepository,
        policy: MarketEnginePolicy,
    ) -> None:
        self.repo = repo
        self.default_scheduler_on = policy.asset_scheduler_on
        self.default_scheduler_seconds = policy.asset_interval
        self.default_agg_type = AggregationType(policy.aggregation)
        self.usd_scheduler_on = policy.usd_scheduler_on
        self.usd_scheduler_seconds = policy.usd_interval

    @handle_conflicts
    @transactional
    async def create_default(
        self,
        asset_id: int,
        code: AssetCode,
    ) -> AssetConfigModel:
        """
        Desc: Create the default config of a newly created asset.
        Args:
            asset_id (int): ID of the owning asset.
            code (AssetCode): Code of the owning asset.
        Returns:
            return (AssetConfigModel): The created config.
        """
        configs = await self.create_defaults({asset_id: code})
        return configs[0]

    @handle_conflicts
    @transactional
    async def create_defaults(
        self, assets: Mapping[int, AssetCode]
    ) -> Sequence[AssetConfigModel]:
        """Create defaults for new assets, including the USD schedule."""
        configs = await self.repo.bulk_create(
            [
                AssetConfigModel(
                    asset_id=id,
                    scheduler_on=(
                        self.usd_scheduler_on
                        if code == AssetCode.USD
                        else self.default_scheduler_on
                    ),
                    scheduler_seconds=(
                        self.usd_scheduler_seconds
                        if code == AssetCode.USD
                        else self.default_scheduler_seconds
                    ),
                    agg_type=self.default_agg_type,
                )
                for id, code in assets.items()
            ]
        )
        return configs

    @handle_conflicts
    @transactional
    async def update(
        self,
        asset_id: int,
        data: AssetConfigUpdate,
    ) -> AssetConfigModel:
        """
        Desc: Patch an asset's config.
        Args:
            asset_id (int): ID of the owning asset.
            data (AssetConfigUpdate): The fields to change.
        Returns:
            return (AssetConfigModel): The updated config.
        """
        row = self._check_not_empty_dict(data.to_row())
        config = await self.repo.update_by_asset_id(asset_id, row)
        config = self._check_for_existence("asset_id", asset_id, config)
        return config

    async def get_by_asset_id(self, asset_id: int) -> AssetConfigModel:
        """
        Desc: Get an asset's config.
        Args:
            asset_id (int): ID of the owning asset.
        Returns:
            return (AssetConfigModel): The found config.
        """
        config = await self.repo.get_by_asset_id(asset_id)
        config = self._check_for_existence("asset_id", asset_id, config)
        return config

    async def get_all(self) -> Sequence[AssetConfigModel]:
        """
        Desc: Get every asset config.
        Returns:
            return (Sequence[AssetConfigModel]): All configs.
        """
        configs = await self.repo.get_all()
        return configs


class AssetSwitchService(IDChecks[AssetSwitchModel]):
    entity = "AssetSwitch"

    def __init__(self, repo: AssetSwitchRepository) -> None:
        self.repo = repo

    def _check_no_repeat(
        self,
        switches: Sequence[SourceSwitch],
        loc: str,
    ) -> Sequence[SourceSwitch]:
        """
        Desc: Refuse an order that names the same market twice.
        Args:
            switches (Sequence[SourceSwitch]): The markets given.
            loc (str): The input field the markets came from.
        Returns:
            return (Sequence[SourceSwitch]): The same markets.
        """
        if len(set(switches)) != len(switches):
            raise ValidationException(
                message="A market may appear once in the order",
                message_code=resources.ASSET_SWITCH_DUPLICATED,
                loc=["body", loc],
                input=[switch.value for switch in switches],
            )
        return switches

    @handle_conflicts
    @transactional
    async def create(
        self,
        asset_id: int,
        data: AssetSwitchCreate,
    ) -> AssetSwitchModel:
        """
        Desc: Add one market to an asset's pricing order.
        Args:
            asset_id (int): ID of the owning asset.
            data (AssetSwitchCreate): The market and its level.
        Returns:
            return (AssetSwitchModel): The created row.
        """
        row = await self.repo.create(
            AssetSwitchModel(
                asset_id=asset_id,
                switch=data.switch,
                priority=data.priority,
            )
        )
        return row

    @handle_conflicts
    @transactional
    async def batch_create(
        self,
        asset_id: int,
        data: AssetSwitchBatchCreate,
    ) -> Sequence[AssetSwitchModel]:
        """
        Desc: Give an asset the markets it is priced from.
        Args:
            asset_id (int): ID of the owning asset.
            data (AssetSwitchBatchCreate): The markets and their levels.
        Returns:
            return (Sequence[AssetSwitchModel]): The created rows.
        """
        rows = await self.batch_create_many({asset_id: data})
        return rows

    @handle_conflicts
    @transactional
    async def batch_create_many(
        self, assets: Mapping[int, AssetSwitchBatchCreate]
    ) -> Sequence[AssetSwitchModel]:
        """Create validated switches for multiple assets in one write."""
        for data in assets.values():
            items = self._check_not_empty_list(data.items)
            self._check_no_repeat([item.switch for item in items], "items")
        rows = await self.repo.bulk_create(
            [
                AssetSwitchModel(
                    asset_id=id, switch=item.switch, priority=item.priority
                )
                for id, data in assets.items()
                for item in data.items
            ]
        )
        return rows

    @handle_conflicts
    @transactional
    async def update(
        self,
        asset_id: int,
        id: int,
        data: AssetSwitchUpdate,
    ) -> AssetSwitchModel:
        """
        Desc: Patch one row of an asset's pricing order.
        Args:
            asset_id (int): ID of the owning asset.
            id (int): ID of the row.
            data (AssetSwitchUpdate): The fields to change.
        Returns:
            return (AssetSwitchModel): The updated row.
        """
        patch = self._check_not_empty_dict(data.to_row())
        row = await self.repo.update_by_asset_and_id(asset_id, id, patch)
        row = self._check_for_id_existence(id, row)
        return row

    @handle_conflicts
    @transactional
    async def batch_update(
        self,
        asset_id: int,
        data: AssetSwitchBatchUpdate,
    ) -> Sequence[AssetSwitchModel]:
        """
        Desc: Give each market of an asset its own priority level.
        Args:
            asset_id (int): ID of the owning asset.
            data (AssetSwitchBatchUpdate): The markets and their levels.
        Returns:
            return (Sequence[AssetSwitchModel]): The written rows.
        """
        items = self._check_not_empty_list(data.items)
        self._check_no_repeat([item.switch for item in items], "items")
        rows = await self.repo.update_priorities(
            asset_id,
            [
                AssetSwitchModel.patch(
                    asset_id=asset_id,
                    switch=item.switch,
                    priority=item.priority,
                )
                for item in items
            ],
        )
        return rows

    @handle_conflicts
    @transactional
    async def set_priority(
        self,
        asset_id: int,
        data: AssetSwitchPriorityUpdate,
    ) -> Sequence[AssetSwitchModel]:
        """
        Desc: Move several markets of an asset onto one priority level.
        Args:
            asset_id (int): ID of the owning asset.
            data (AssetSwitchPriorityUpdate): The level and its markets.
        Returns:
            return (Sequence[AssetSwitchModel]): The moved rows.
        """
        switches = self._check_not_empty_list(data.switches)
        self._check_no_repeat(switches, "switches")
        rows = await self.repo.update_priorities(
            asset_id,
            [
                AssetSwitchModel.patch(
                    asset_id=asset_id,
                    switch=switch,
                    priority=data.priority,
                )
                for switch in switches
            ],
        )
        return rows

    @handle_conflicts
    @transactional
    async def remove(self, asset_id: int, id: int) -> AssetSwitchModel:
        """
        Desc: Drop one market from an asset's pricing order.
        Args:
            asset_id (int): ID of the owning asset.
            id (int): ID of the row.
        Returns:
            return (AssetSwitchModel): The deleted row.
        """
        row = await self.repo.delete_by_asset_and_id(asset_id, id)
        row = self._check_for_id_existence(id, row)
        return row

    @handle_conflicts
    @transactional
    async def batch_remove(
        self,
        asset_id: int,
        data: AssetSwitchBatchDelete,
    ) -> BatchResultType[AssetSwitchModel, ValidationException]:
        """
        Desc: Drop several markets from an asset's pricing order, saying
        which of them were not this asset's to drop.
        Args:
            asset_id (int): ID of the owning asset.
            data (AssetSwitchBatchDelete): IDs of the rows to drop.
        Returns:
            return (BatchResultType[AssetSwitchModel, ValidationException]):
                The deleted rows, and an error for each id that named
                nothing this asset owns.
        """
        ids = self._check_not_empty_list(data.ids)
        rows = await self.repo.delete_by_asset_and_ids(asset_id, ids)
        return self._check_batch_data(ids, rows)

    async def get_by_asset_id(
        self,
        asset_id: int,
    ) -> Sequence[AssetSwitchModel]:
        """
        Desc: Get an asset's markets in pricing order.
        Args:
            asset_id (int): ID of the owning asset.
        Returns:
            return (Sequence[AssetSwitchModel]): The markets, best first.
        """
        rows = await self.repo.get_by_asset_id(asset_id)
        return rows


class AssetService(IDChecks[AssetModel]):
    entity = "Asset"

    def __init__(
        self,
        repo: AssetRepository,
    ) -> None:
        self.repo = repo

    @handle_conflicts
    @transactional
    async def create(self, data: AssetCreate) -> AssetModel:
        """
        Desc: Create an asset.
        Args:
            data (AssetCreate): Validated payload to persist.
        Returns:
            return (AssetModel): The created asset.
        """
        asset = await self.repo.create(
            AssetModel.patch(**data.to_row(exclude_unset=False))
        )
        return asset

    @handle_conflicts
    @transactional
    async def update(self, id: int, data: AssetUpdate) -> AssetModel:
        """
        Desc: Patch an asset by id.
        Args:
            id (int): ID of the asset.
            data (AssetUpdate): The fields to change.
        Returns:
            return (AssetModel): The updated asset.
        """
        row = self._check_not_empty_dict(data.to_row())
        await self.repo.update_by_id(id, row)
        asset = await self.repo.get_by_id(id)
        asset = self._check_for_id_existence(id, asset)
        return asset

    async def get_by_id(self, id: int) -> AssetModel:
        """
        Desc: Get an asset by id.
        Args:
            id (int): ID of the asset.
        Returns:
            return (AssetModel): The found asset.
        """
        asset = await self.repo.get_by_id(id)
        asset = self._check_for_id_existence(id, asset)
        return asset

    async def get_by_ids(
        self,
        ids: list[int],
    ) -> Sequence[AssetModel]:
        """
        Desc: Get the assets the given ids belong to.
        Args:
            ids (list[int]): IDs of the assets to read.
        Returns:
            return (Sequence[AssetModel]): The assets that exist.
        """
        assets = await self.repo.get_by_ids(ids)
        return assets

    async def get_all(self) -> Sequence[AssetModel]:
        """
        Desc: Get every asset.
        Returns:
            return (Sequence[AssetModel]): All assets.
        """
        assets = await self.repo.get_all()
        return assets

    async def get_by_code(self, code: AssetCode) -> AssetModel:
        """
        Desc: Get one asset by its code.
        Args:
            code (AssetCode): The asset's code.
        Returns:
            return (AssetModel): The found asset.
        """
        asset = await self.repo.get_by_code(code)
        asset = self._check_for_existence("code", code, asset)
        return asset

    @handle_conflicts
    @transactional
    async def remove(self, id: int) -> AssetModel:
        """
        Desc: Delete an asset by id, its config cascading with it.
        Args:
            id (int): ID of the asset.
        Returns:
            return (AssetModel): The deleted asset.
        """
        asset = await self.repo.get_by_id(id)
        await self.repo.remove_by_id(id)
        asset = self._check_for_id_existence(id, asset)
        return asset

    async def get_batch(
        self,
        ids: list[int],
    ) -> BatchResultType[AssetModel, ValidationException]:
        """
        Desc: Get many assets at once, saying which of the ids nothing
            answered to.
        Args:
            ids (list[int]): IDs of the assets.
        Returns:
            return (BatchResultType): What was found, and an error per id
                that was not.
        """
        found = await self.repo.get_by_ids(ids)
        batch = self._check_batch_data(ids, found)
        return batch


class AssetMetaService:
    def __init__(self, assets: IAssetService) -> None:
        self.assets = assets

    async def build(self, asset_ids: Sequence[int]) -> AssetsMetaModel:
        """
        Desc: Name the assets the given ids belong to.
        Args:
            asset_ids (Sequence[int]): IDs of the assets to name.
        Returns:
            return (AssetsMetaModel): One entry per asset that exists.
        """
        assets = await self.assets.get_by_ids(list(asset_ids))
        return AssetsMetaModel(assets=AssetMetaModel.from_objs(assets))


class AssetSourcePriceService:
    def __init__(
        self,
        symbols: ISymbolService,
        readings: ISourceCacheReaderService,
        meta: ISourceMetaService,
    ) -> None:
        self.symbols = symbols
        self.readings = readings
        self.meta = meta

    async def get_by_asset_id(self, asset_id: int) -> AssetSourcePriceResult:
        """
        Desc: Say which sources are quoting an asset right now, by taking
            the asset's lines and reading what the last crawl left for
            each of them.
        Args:
            asset_id (int): ID of the asset being asked about.
        Returns:
            return (AssetSourcePriceResult): One price per source and
                line, and the names of both.
        """
        symbols = await self.symbols.get_by_asset_id(asset_id)
        readings = await self.readings.get_many_by_symbols(
            [SymbolCode(symbol.code) for symbol in symbols]
        )
        rows = [row for group in readings.values() for row in group]
        meta = await self.meta.build_by_symbols(
            source_ids=list({row.source_id for row in rows}),
            symbols=symbols,
        )
        return AssetSourcePriceResult(
            data=AdminSourcePriceModel.from_objs(rows), meta=meta
        )
