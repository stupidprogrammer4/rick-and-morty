from collections.abc import Awaitable
from typing import Protocol, Sequence

from papilio.errors.exceptions import ValidationException
from papilio.schemas.results import BatchResultType

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.bubbles.domain.dtos import (
    BubbleConfigUpdate,
    BubbleCreate,
    BubbleUpdate,
)
from src.modules.pricing.bubbles.domain.models import (
    BubbleConfigModel,
    BubbleModel,
    BubbleWithConfigModel,
)
from src.modules.pricing.bubbles.domain.results import BubbleSourcesResult


class IBubbleConfigService(Protocol):
    def create_default(
        self, bubble_id: int
    ) -> Awaitable[BubbleConfigModel]: ...

    def create_defaults(
        self, bubble_ids: Sequence[int]
    ) -> Awaitable[Sequence[BubbleConfigModel]]: ...

    def update(
        self,
        bubble_id: int,
        data: BubbleConfigUpdate,
    ) -> Awaitable[BubbleConfigModel]: ...

    def get_by_bubble_id(
        self, bubble_id: int
    ) -> Awaitable[BubbleConfigModel]: ...

    def get_all(self) -> Awaitable[Sequence[BubbleConfigModel]]: ...


class IBubbleService(Protocol):
    def create(self, data: BubbleCreate) -> Awaitable[BubbleModel]: ...

    def update(
        self, id: int, data: BubbleUpdate
    ) -> Awaitable[BubbleModel]: ...

    def get_by_id(self, id: int) -> Awaitable[BubbleModel]: ...

    def get_all(self) -> Awaitable[Sequence[BubbleModel]]: ...

    def remove(self, id: int) -> Awaitable[BubbleModel]: ...

    def get_batch(
        self,
        ids: list[int],
    ) -> Awaitable[BatchResultType[BubbleModel, ValidationException]]: ...


class IBubbleSourceService(Protocol):
    def get_by_asset_code(
        self, code: AssetCode
    ) -> Awaitable[BubbleSourcesResult]: ...


class ICreateBubble(Protocol):
    def execute(self, data: BubbleCreate) -> Awaitable[BubbleModel]: ...


class IUpdateBubbleConfig(Protocol):
    def execute(
        self, bubble_id: int, data: BubbleConfigUpdate
    ) -> Awaitable[BubbleConfigModel]: ...


class IGetBubblesWithConfig(Protocol):
    def execute(self) -> Awaitable[Sequence[BubbleWithConfigModel]]: ...
