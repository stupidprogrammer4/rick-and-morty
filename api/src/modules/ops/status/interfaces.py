from collections.abc import Awaitable
from typing import Protocol

from src.modules.ops.status.domain.dtos import PortalStatus


class IPortalStatusQuery(Protocol):
    def get(self) -> Awaitable[PortalStatus]: ...
