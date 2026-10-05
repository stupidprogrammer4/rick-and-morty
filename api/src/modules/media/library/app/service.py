from collections.abc import Sequence
from datetime import timedelta

from portal_contracts.media import MediaPolicy
from src.modules.media.library.domain.dtos import MediaCacheEntry
from src.modules.media.library.domain.models import MediaAssetModel
from src.modules.media.library.infra.mysql import MediaAssetRepository
from src.modules.media.sources.domain.dtos import DownloadedFile
from src.shared.dates import utc_now


class MediaAssetService:
    def __init__(self, repository: MediaAssetRepository, policy: MediaPolicy):
        self.repository = repository
        self.policy = policy

    def downloaded(self, row: MediaAssetModel) -> DownloadedFile:
        return DownloadedFile.model_validate_json(row.payload).model_copy(
            update={"file_id": row.file_id}
        )

    async def get(self, key: str) -> DownloadedFile | None:
        row = await self.repository.get(key, utc_now())
        return self.downloaded(row) if row is not None else None

    async def get_many(self, keys: Sequence[str]) -> list[MediaCacheEntry]:
        rows = await self.repository.get_many(keys, utc_now())
        return [
            MediaCacheEntry(key=row.cache_key, downloaded=self.downloaded(row))
            for row in rows
        ]

    async def store(self, bot_id: int, downloaded: DownloadedFile) -> None:
        if (
            not self.policy.file_cache_seconds
            or not downloaded.cache_key
            or not downloaded.file_id
        ):
            return
        await self.repository.store(
            MediaAssetModel(
                bot_id=bot_id,
                cache_key=downloaded.cache_key,
                file_id=downloaded.file_id,
                payload=downloaded.model_dump_json(),
                expires_at=utc_now()
                + timedelta(seconds=self.policy.file_cache_seconds),
            )
        )

    async def invalidate(self, key: str) -> None:
        await self.repository.invalidate(key)

    async def prune(self) -> None:
        await self.repository.prune(utc_now())
