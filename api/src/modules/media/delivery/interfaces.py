from collections.abc import Awaitable
from typing import Protocol

from portal_contracts.media import (
    MediaFileDelivery,
    MediaFileResult,
)


class IMediaGateway(Protocol):
    def send(self, data: MediaFileDelivery) -> Awaitable[MediaFileResult]: ...
    def notify(self, owner_id: int, text: str) -> Awaitable[None]: ...
