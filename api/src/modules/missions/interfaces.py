from collections.abc import Awaitable
from typing import Protocol

from portal_contracts.missions import (
    MissionAccepted,
    MissionCreate,
    MissionOut,
    MissionPage,
    PageRequest,
)
from src.modules.missions.domain.dtos import ScheduledMissionCreate


class IMissionService(Protocol):
    def create_scheduled(
        self, data: ScheduledMissionCreate
    ) -> Awaitable[None]: ...
    def create(self, data: MissionCreate) -> Awaitable[MissionAccepted]: ...
    def get(self, id: int, owner_id: int) -> Awaitable[MissionOut]: ...
    def page(
        self, owner_id: int, data: PageRequest
    ) -> Awaitable[MissionPage]: ...
    def cancel(self, id: int, owner_id: int) -> Awaitable[MissionOut]: ...


class IMissionExecutor(Protocol):
    def execute(self, mission_id: int) -> Awaitable[None]: ...


class IMissionRecovery(Protocol):
    def enqueue_pending(self) -> Awaitable[None]: ...


class IMissionAdmission(Protocol):
    def accept(self, data: MissionCreate) -> Awaitable[MissionAccepted]: ...


class IScheduledMissionCommands(Protocol):
    def tick(self) -> Awaitable[None]: ...
