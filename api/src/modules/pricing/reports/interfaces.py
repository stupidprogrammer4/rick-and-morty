from collections.abc import Awaitable
from datetime import datetime
from typing import Protocol

from portal_contracts.content import PublicationPages
from src.modules.content.drafts.domain.models import DraftModel
from src.modules.pricing.reports.domain.dtos import MarketSnapshot
from src.modules.pricing.reports.domain.models import MarketSnapshotModel


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


class IMarketPublicationQuery(Protocol):
    def render_pages(
        self, draft: DraftModel
    ) -> Awaitable[PublicationPages | None]: ...
    async def validate(self, draft: DraftModel, now: datetime) -> None: ...
