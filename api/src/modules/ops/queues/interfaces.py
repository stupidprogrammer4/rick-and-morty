from collections.abc import Awaitable
from typing import Protocol


class ITaskHistoryMaintenance(Protocol):
    def clean(self) -> Awaitable[int]: ...
