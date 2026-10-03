from collections.abc import Awaitable
from typing import Any, Protocol


class IBackendClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        owner_id: int,
        *,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Awaitable[Any]: ...
