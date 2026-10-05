from collections.abc import Awaitable, Sequence
from typing import Protocol

from src.modules.media.library.domain.dtos import MediaCacheEntry
from src.modules.media.sources.domain.dtos import DownloadedFile


class IMediaAssetService(Protocol):
    def get(self, key: str) -> Awaitable[DownloadedFile | None]: ...
    def get_many(
        self, keys: Sequence[str]
    ) -> Awaitable[list[MediaCacheEntry]]: ...
    def store(
        self, bot_id: int, downloaded: DownloadedFile
    ) -> Awaitable[None]: ...
    def invalidate(self, key: str) -> Awaitable[None]: ...
    def prune(self) -> Awaitable[None]: ...
