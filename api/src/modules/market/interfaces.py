from collections.abc import Awaitable
from datetime import datetime
from typing import Protocol

from portal_contracts.content import DraftOut, PublicationPages
from src.modules.content.domain.models import DraftModel
from src.modules.market.domain.dtos import MarketSnapshot
from src.modules.market.domain.models import MarketSnapshotModel
from src.modules.missions.domain.models import MissionModel


class IPriceProvider(Protocol):
    def fetch(self) -> Awaitable[MarketSnapshot]: ...


class IMarketQuery(Protocol):
    def report(self) -> Awaitable[str]: ...
    def snapshot(self) -> Awaitable[MarketSnapshot]: ...


class IMarketSnapshotService(Protocol):
    async def create(
        self, data: MarketSnapshotModel
    ) -> MarketSnapshotModel: ...
    async def get(self, id: int, owner_id: int) -> MarketSnapshotModel: ...


class IMarketDraftCommands(Protocol):
    async def from_snapshot(
        self, mission: MissionModel, snapshot: MarketSnapshot
    ) -> DraftOut: ...


class IMarketPublicationQuery(Protocol):
    def render_pages(
        self, draft: DraftModel
    ) -> Awaitable[PublicationPages | None]: ...
    async def validate(self, draft: DraftModel, now: datetime) -> None: ...
