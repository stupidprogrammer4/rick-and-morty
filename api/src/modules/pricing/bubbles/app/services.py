from typing import Sequence

from papilio.core import resources as framework_resources
from papilio.errors.exceptions import NotFoundException, ValidationException
from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional
from papilio.schemas.results import BatchResultType
from papilio.tools.checks import Checks, IDChecks

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.bubbles.domain.dtos import (
    BubbleConfigUpdate,
    BubbleCreate,
    BubbleUpdate,
)
from src.modules.pricing.bubbles.domain.models import (
    BubbleConfigModel,
    BubbleModel,
)
from src.modules.pricing.bubbles.domain.results import BubbleSourcesResult
from src.modules.pricing.bubbles.infra.mysql import (
    BubbleConfigRepository,
    BubbleRepository,
)
from src.modules.pricing.engine.interfaces import (
    ICacheReaderService as ISourceCacheReaderService,
)
from src.modules.pricing.sources.domain.models import SourceBubbleModel
from src.modules.pricing.sources.interfaces import ISourceMetaService


class BubbleConfigService(Checks[BubbleConfigModel]):
    entity = "BubbleConfig"

    def __init__(
        self,
        repo: BubbleConfigRepository,
        policy: MarketEnginePolicy,
    ) -> None:
        self.repo = repo
        self.default_scheduler_on = policy.bubble_scheduler_on
        self.default_scheduler_seconds = policy.asset_interval
        self.default_agg_type = AggregationType(policy.aggregation)

    @handle_conflicts
    @transactional
    async def create_default(self, bubble_id: int) -> BubbleConfigModel:
        """
        Desc: Create the default config of a newly created bubble.
        Args:
            bubble_id (int): ID of the owning bubble.
        Returns:
            return (BubbleConfigModel): The created config.
        """
        configs = await self.create_defaults([bubble_id])
        return configs[0]

    @handle_conflicts
    @transactional
    async def create_defaults(
        self, bubble_ids: Sequence[int]
    ) -> Sequence[BubbleConfigModel]:
        """Create default configurations in one write."""
        configs = await self.repo.bulk_create(
            [
                BubbleConfigModel(
                    bubble_id=id,
                    scheduler_on=self.default_scheduler_on,
                    scheduler_seconds=self.default_scheduler_seconds,
                    agg_type=self.default_agg_type,
                )
                for id in bubble_ids
            ]
        )
        return configs

    @handle_conflicts
    @transactional
    async def update(
        self,
        bubble_id: int,
        data: BubbleConfigUpdate,
    ) -> BubbleConfigModel:
        """
        Desc: Patch a bubble's config.
        Args:
            bubble_id (int): ID of the owning bubble.
            data (BubbleConfigUpdate): The fields to change.
        Returns:
            return (BubbleConfigModel): The updated config.
        """
        row = self._check_not_empty_dict(data.to_row())
        config = await self.repo.update_by_bubble_id(bubble_id, row)
        config = self._check_for_existence("bubble_id", bubble_id, config)
        return config

    async def get_by_bubble_id(self, bubble_id: int) -> BubbleConfigModel:
        """
        Desc: Get a bubble's config.
        Args:
            bubble_id (int): ID of the owning bubble.
        Returns:
            return (BubbleConfigModel): The found config.
        """
        config = await self.repo.get_by_bubble_id(bubble_id)
        config = self._check_for_existence("bubble_id", bubble_id, config)
        return config

    async def get_all(self) -> Sequence[BubbleConfigModel]:
        """
        Desc: Get every bubble config.
        Returns:
            return (Sequence[BubbleConfigModel]): All configs.
        """
        configs = await self.repo.get_all()
        return configs


class BubbleService(IDChecks[BubbleModel]):
    entity = "Bubble"

    def __init__(
        self,
        repo: BubbleRepository,
    ) -> None:
        self.repo = repo

    @handle_conflicts
    @transactional
    async def create(self, data: BubbleCreate) -> BubbleModel:
        """
        Desc: Persist a bubble.
        Args:
            data (BubbleCreate): Validated payload to persist.
        Returns:
            return (BubbleModel): The created bubble.
        """
        bubble = await self.repo.create(
            BubbleModel(**data.to_row(exclude_unset=False))
        )
        return bubble

    @handle_conflicts
    @transactional
    async def update(self, id: int, data: BubbleUpdate) -> BubbleModel:
        """
        Desc: Patch a bubble by id.
        Args:
            id (int): ID of the bubble.
            data (BubbleUpdate): The fields to change.
        Returns:
            return (BubbleModel): The updated bubble.
        """
        row = self._check_not_empty_dict(data.to_row())
        await self.repo.update_by_id(id, row)
        bubble = await self.repo.get_by_id(id)
        bubble = self._check_for_id_existence(id, bubble)
        return bubble

    async def get_by_id(self, id: int) -> BubbleModel:
        """
        Desc: Get a bubble by id.
        Args:
            id (int): ID of the bubble.
        Returns:
            return (BubbleModel): The found bubble.
        """
        bubble = await self.repo.get_by_id(id)
        bubble = self._check_for_id_existence(id, bubble)
        return bubble

    async def get_all(self) -> Sequence[BubbleModel]:
        """
        Desc: Get every bubble.
        Returns:
            return (Sequence[BubbleModel]): All bubbles.
        """
        bubbles = await self.repo.get_all()
        return bubbles

    @handle_conflicts
    @transactional
    async def remove(self, id: int) -> BubbleModel:
        """
        Desc: Delete a bubble by id, its config cascading with it.
        Args:
            id (int): ID of the bubble.
        Returns:
            return (BubbleModel): The deleted bubble.
        """
        bubble = await self.repo.get_by_id(id)
        await self.repo.remove_by_id(id)
        bubble = self._check_for_id_existence(id, bubble)
        return bubble

    async def get_batch(
        self,
        ids: list[int],
    ) -> BatchResultType[BubbleModel, ValidationException]:
        """
        Desc: Get many bubbles at once, saying which of the ids nothing
            answered to.
        Args:
            ids (list[int]): IDs of the bubbles.
        Returns:
            return (BatchResultType): What was found, and an error per id
                that was not.
        """
        found = await self.repo.get_by_ids(ids)
        batch = self._check_batch_data(ids, found)
        return batch


class BubbleSourceService:
    def __init__(
        self,
        readings: ISourceCacheReaderService,
        meta: ISourceMetaService,
    ) -> None:
        self.readings = readings
        self.meta = meta

    async def get_by_asset_code(self, code: AssetCode) -> BubbleSourcesResult:
        """
        Desc: Say which sources last quoted a bubble on one asset.
        Args:
            code (AssetCode): Code of the asset the bubble is on.
        Returns:
            return (BubbleSourcesResult): The readings, and the sources
                they came from.
        """
        rows = await self.readings.get_bubbles_by_asset(code)
        if not rows:
            raise NotFoundException(
                identifier="code",
                identifier_value=code,
                message=f"No source has bubbled {code} yet",
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Bubble",
            )
        meta = await self.meta.build_sources(
            list({row.source_id for row in rows})
        )
        return BubbleSourcesResult(
            data=SourceBubbleModel.from_objs(rows), meta=meta
        )
