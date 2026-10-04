from collections.abc import Awaitable
from typing import Protocol

from src.modules.content.replies.domain.models import PrivateReplyModel


class IPrivateReplyService(Protocol):
    def create(self, data: PrivateReplyModel) -> Awaitable[None]: ...
    def dispatch(self, id: int) -> Awaitable[None]: ...


class IReplyRecovery(Protocol):
    def enqueue_pending(self) -> Awaitable[None]: ...
