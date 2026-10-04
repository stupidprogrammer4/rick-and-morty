from collections.abc import Awaitable, Sequence
from typing import Protocol

from src.modules.media.storage.domain.dtos import WorkspaceItem


class IMediaWorkspace(Protocol):
    def prepare(self, id: int) -> Awaitable[None]: ...
    def prepare_item(self, job_id: int, item_id: int) -> Awaitable[None]: ...
    def prepare_many(
        self, inputs: Sequence[WorkspaceItem]
    ) -> Awaitable[None]: ...
