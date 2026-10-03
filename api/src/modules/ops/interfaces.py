from collections.abc import Awaitable
from typing import Protocol

from src.modules.ops.domain.dtos import PortalStatus
from src.modules.ops.domain.models import PortalGuardModel


class IPortalGuard(Protocol):
    def lock(self, key: str) -> Awaitable[PortalGuardModel]: ...
    def is_paused(self) -> Awaitable[bool]: ...
    def pause(self, paused: bool) -> Awaitable[None]: ...


class IPortalStatusQuery(Protocol):
    def get(self) -> Awaitable[PortalStatus]: ...
