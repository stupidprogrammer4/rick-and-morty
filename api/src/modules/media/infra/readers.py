from collections.abc import Sequence
from datetime import datetime

from papilio.infra.db.uow import MySQLUnitOfWork
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlmodel import col

from portal_contracts.media import (
    MediaItemOut,
    MediaItemPage,
    MediaJobOut,
    MediaJobPage,
)
from src.modules.media.domain.dtos import MediaDownloadInput
from src.modules.media.domain.models import MediaItemModel, MediaJobModel
from src.modules.media.infra.tables import MediaItemTable, MediaJobTable


class MediaAdmissionCounts(BaseModel):
    active_user: int
    active_global: int
    recent_user: int


class MediaItemCounts(BaseModel):
    sent: int = 0
    failed: int = 0
    unknown: int = 0
    pending: int = 0


class MediaOccupiedCounts(BaseModel):
    transfers: int
    buffered: int
    plans: int


class MediaTransferTicket(BaseModel):
    item_id: int
    job_id: int


class MediaReader:
    def __init__(self, uow: MySQLUnitOfWork):
        self.uow = uow

    async def admission(
        self, owner_id: int, since: datetime
    ) -> MediaAdmissionCounts:
        active = col(MediaJobTable.status).in_(
            ["queued", "planning", "running"]
        )
        result = await self.uow.execute(
            select(func.count()).select_from(MediaJobTable).where(active)
        )
        global_count = result.scalar_one()
        result = await self.uow.execute(
            select(func.count())
            .select_from(MediaJobTable)
            .where(active, col(MediaJobTable.owner_id) == owner_id)
        )
        user_count = result.scalar_one()
        result = await self.uow.execute(
            select(func.count())
            .select_from(MediaJobTable)
            .where(
                col(MediaJobTable.owner_id) == owner_id,
                col(MediaJobTable.created_at) >= since,
            )
        )
        return MediaAdmissionCounts(
            active_user=user_count,
            active_global=global_count,
            recent_user=result.scalar_one(),
        )

    async def jobs(
        self, owner_id: int, page: int, per_page: int
    ) -> MediaJobPage:
        predicate = col(MediaJobTable.owner_id) == owner_id
        result = await self.uow.execute(
            select(MediaJobTable)
            .where(predicate)
            .order_by(col(MediaJobTable.id).desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = [
            MediaJobOut.model_validate(row, from_attributes=True)
            for row in result.scalars().all()
        ]
        result = await self.uow.execute(
            select(func.count()).select_from(MediaJobTable).where(predicate)
        )
        return MediaJobPage(
            items=items,
            total=result.scalar_one(),
            page=page,
            per_page=per_page,
        )

    async def items(
        self, job_id: int, page: int, per_page: int
    ) -> MediaItemPage:
        predicate = col(MediaItemTable.job_id) == job_id
        result = await self.uow.execute(
            select(MediaItemTable)
            .where(predicate)
            .order_by(col(MediaItemTable.position))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = [
            MediaItemOut.model_validate(row, from_attributes=True)
            for row in result.scalars().all()
        ]
        result = await self.uow.execute(
            select(func.count()).select_from(MediaItemTable).where(predicate)
        )
        return MediaItemPage(
            items=items,
            total=result.scalar_one(),
            page=page,
            per_page=per_page,
        )

    async def counts(self, job_id: int) -> MediaItemCounts:
        result = await self.uow.execute(
            select(col(MediaItemTable.status), func.count())
            .where(col(MediaItemTable.job_id) == job_id)
            .group_by(col(MediaItemTable.status))
        )
        values = {status: count for status, count in result.all()}
        return MediaItemCounts(
            sent=values.get("sent", 0),
            failed=values.get("failed", 0),
            unknown=values.get("unknown", 0),
            pending=sum(
                values.get(status, 0)
                for status in (
                    "queued",
                    "reserved",
                    "downloading",
                    "ready",
                    "sending",
                )
            ),
        )

    async def occupied(self, now: datetime) -> MediaOccupiedCounts:
        result = await self.uow.execute(
            select(col(MediaItemTable.status), func.count())
            .where(
                col(MediaItemTable.status).in_(
                    ["reserved", "downloading", "ready", "sending"]
                )
            )
            .group_by(col(MediaItemTable.status))
        )
        counts = {status: count for status, count in result.all()}
        result = await self.uow.execute(
            select(func.count())
            .select_from(MediaJobTable)
            .where(
                or_(
                    col(MediaJobTable.status) == "planning",
                    (col(MediaJobTable.status) == "queued")
                    & (col(MediaJobTable.total) == 0)
                    & (col(MediaJobTable.lease_until) > now),
                )
            )
        )
        return MediaOccupiedCounts(
            transfers=counts.get("reserved", 0) + counts.get("downloading", 0),
            buffered=counts.get("ready", 0) + counts.get("sending", 0),
            plans=result.scalar_one(),
        )

    async def ready_items(
        self, now: datetime, limit: int
    ) -> list[MediaTransferTicket]:
        result = await self.uow.execute(
            select(col(MediaItemTable.id), col(MediaItemTable.job_id))
            .join(
                MediaJobTable,
                col(MediaItemTable.job_id) == col(MediaJobTable.id),
            )
            .where(
                col(MediaJobTable.status).in_(["queued", "running"]),
                col(MediaItemTable.status) == "queued",
                or_(
                    col(MediaItemTable.available_at).is_(None),
                    col(MediaItemTable.available_at) <= now,
                ),
            )
            .order_by(col(MediaJobTable.id), col(MediaItemTable.position))
            .limit(limit)
        )
        return [
            MediaTransferTicket(item_id=item_id, job_id=job_id)
            for item_id, job_id in result.all()
        ]

    async def finished_jobs(self) -> list[int]:
        pending = select(col(MediaItemTable.job_id)).where(
            col(MediaItemTable.status).in_(
                ["queued", "reserved", "downloading", "ready", "sending"]
            )
        )
        result = await self.uow.execute(
            select(col(MediaJobTable.id)).where(
                col(MediaJobTable.total) > 0,
                col(MediaJobTable.status).in_(["queued", "running"]),
                col(MediaJobTable.id).not_in(pending),
            )
        )
        return list(result.scalars().all())

    async def active_ids(self) -> set[int]:
        result = await self.uow.execute(
            select(col(MediaJobTable.id)).where(
                col(MediaJobTable.status).in_(["planning", "running"])
            )
        )
        return set(result.scalars().all())

    async def ready_deliveries(self, now: datetime) -> list[int]:
        result = await self.uow.execute(
            select(col(MediaItemTable.job_id))
            .where(
                col(MediaItemTable.status) == "ready",
                or_(
                    col(MediaItemTable.available_at).is_(None),
                    col(MediaItemTable.available_at) <= now,
                ),
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def transfers(self, ids: Sequence[int]) -> list[MediaDownloadInput]:
        if not ids:
            return []
        result = await self.uow.execute(
            select(MediaJobTable, MediaItemTable)
            .join(
                MediaItemTable,
                col(MediaItemTable.job_id) == col(MediaJobTable.id),
            )
            .where(col(MediaItemTable.id).in_(ids))
            .order_by(col(MediaJobTable.id), col(MediaItemTable.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [
            MediaDownloadInput(
                job=MediaJobModel.model_validate(job, from_attributes=True),
                item=MediaItemModel.model_validate(item, from_attributes=True),
            )
            for job, item in result.all()
        ]
