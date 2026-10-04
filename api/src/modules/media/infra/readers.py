from datetime import datetime

from papilio.infra.db.uow import MySQLUnitOfWork
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlmodel import col

from portal_contracts.media import (
    MediaItemOut,
    MediaItemPage,
    MediaJobOut,
    MediaJobPage,
)
from src.modules.media.infra.tables import MediaItemTable, MediaJobTable


class MediaAdmissionCounts(BaseModel):
    active_user: int
    active_global: int
    recent_user: int


class MediaItemCounts(BaseModel):
    sent: int = 0
    failed: int = 0
    unknown: int = 0


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
        )

    async def active_ids(self) -> set[int]:
        result = await self.uow.execute(
            select(col(MediaJobTable.id)).where(
                col(MediaJobTable.status).in_(["planning", "running"])
            )
        )
        return set(result.scalars().all())
