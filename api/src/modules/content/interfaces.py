from collections.abc import Awaitable
from typing import Protocol

from portal_contracts.content import (
    DraftCreate,
    DraftDecision,
    DraftEdit,
    DraftOut,
    DraftPage,
)
from portal_contracts.enums import BotRole
from portal_contracts.missions import PageRequest
from src.modules.content.domain.models import DraftModel


class IDraftService(Protocol):
    def create(
        self,
        owner_id: int,
        origin_bot: BotRole,
        data: DraftCreate,
        *,
        key: str,
        mission_id: int | None = None,
        synthetic: bool = False,
        market_snapshot_id: int | None = None,
    ) -> Awaitable[DraftOut]: ...
    def get(self, id: int, owner_id: int) -> Awaitable[DraftOut]: ...
    def locked(self, id: int, owner_id: int) -> Awaitable[DraftModel]: ...
    def page(
        self, owner_id: int, data: PageRequest
    ) -> Awaitable[DraftPage]: ...
    def edit(
        self, id: int, owner_id: int, data: DraftEdit
    ) -> Awaitable[DraftOut]: ...
    def decide(
        self, id: int, owner_id: int, data: DraftDecision, *, approve: bool
    ) -> Awaitable[DraftOut]: ...


class IDraftAdmission(Protocol):
    async def create_manual(
        self, owner_id: int, origin_bot: BotRole, data: DraftCreate, key: str
    ) -> DraftOut: ...
