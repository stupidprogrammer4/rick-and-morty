from collections.abc import Sequence
from datetime import datetime

from portal_contracts.media import MediaAccepted, MediaCreate, MediaJobOut
from src.modules.media.downloads.domain.dtos import (
    MediaItemChange,
    MediaJobChange,
)
from src.modules.media.downloads.domain.models import (
    MediaItemModel,
    MediaJobModel,
)
from src.modules.media.downloads.infra.mysql import (
    MediaItemRepository,
    MediaJobRepository,
)
from src.modules.media.sources.domain.dtos import DownloadPlan
from src.shared.dates import utc_now
from src.shared.errors import missing


class MediaJobService:
    def __init__(self, repo: MediaJobRepository):
        self.repo = repo

    async def record(self, id: int, lock: bool = False) -> MediaJobModel:
        record = await self.repo.get(id, lock)
        if record is None:
            raise missing("media_job", id)
        return record

    async def get(self, id: int, owner_id: int) -> MediaJobOut:
        row = await self.record(id)
        if row.owner_id != owner_id:
            raise missing("media_job", id)
        return MediaJobOut.model_validate(row, from_attributes=True)

    async def create(self, data: MediaCreate, provider: str) -> MediaAccepted:
        row = await self.repo.by_update(data.bot_id, data.update_id)
        if row is not None:
            if (
                row.owner_id != data.owner_id
                or row.url != data.url
                or row.mode != data.mode
            ):
                raise missing("media_job", row.id)
            return MediaAccepted(
                job=MediaJobOut.model_validate(row, from_attributes=True),
                duplicate=True,
            )
        row = await self.repo.create(
            MediaJobModel(**data.model_dump(), provider=provider)
        )
        return MediaAccepted(
            job=MediaJobOut.model_validate(row, from_attributes=True)
        )

    async def change(self, id: int, data: MediaJobChange) -> None:
        await self.repo.change(id, data)

    async def due(self, limit: int) -> Sequence[MediaJobModel]:
        result = await self.repo.due(limit, utc_now())
        return result

    async def expired(self, now: datetime) -> Sequence[MediaJobModel]:
        result = await self.repo.expired(now)
        return result

    async def requeue_many(self, ids: Sequence[int]) -> None:
        await self.repo.requeue_many(ids)

    async def dispatch_many(
        self, ids: Sequence[int], lease_until: datetime
    ) -> None:
        await self.repo.dispatch_many(ids, lease_until)

    async def start_many(self, ids: Sequence[int]) -> None:
        await self.repo.start_many(ids)


class MediaItemService:
    def __init__(self, repo: MediaItemRepository):
        self.repo = repo

    async def create_many(self, job_id: int, plan: DownloadPlan) -> None:
        await self.repo.insert_items(
            [
                MediaItemModel(
                    job_id=job_id,
                    position=position,
                    title=item.title[:200],
                    payload=item.model_dump_json(),
                    source_url=item.source_url[:2048],
                )
                for position, item in enumerate(plan.items, 1)
            ]
        )

    async def next(self, job_id: int) -> MediaItemModel | None:
        result = await self.repo.next(job_id)
        return result

    async def next_delivery(self, job_id: int) -> MediaItemModel | None:
        result = await self.repo.next_delivery(job_id)
        return result

    async def ready(self, job_id: int) -> MediaItemModel | None:
        result = await self.repo.ready(job_id)
        return result

    async def get(self, id: int, lock: bool = False) -> MediaItemModel:
        result = await self.repo.get(id, lock)
        if result is None:
            raise missing("media_item", id)
        return result

    async def change(self, id: int, data: MediaItemChange) -> None:
        await self.repo.change(id, data)

    async def interrupt(self, job_id: int) -> None:
        await self.repo.interrupt(job_id)

    async def interrupt_many(self, ids: Sequence[int]) -> None:
        await self.repo.interrupt_many(ids)

    async def reserve_many(
        self, ids: Sequence[int], lease_until: datetime
    ) -> None:
        await self.repo.reserve_many(ids, lease_until)

    async def recover(self, now: datetime) -> None:
        await self.repo.recover(now)

    async def save_many(self, rows: Sequence[MediaItemModel]) -> None:
        await self.repo.save_many(rows)
