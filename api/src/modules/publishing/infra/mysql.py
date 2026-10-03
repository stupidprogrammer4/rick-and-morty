from collections.abc import Sequence
from datetime import date, datetime

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlmodel import col

from src.modules.publishing.domain.models import (
    PrivateReplyModel,
    PublicationModel,
)
from src.modules.publishing.infra.tables import (
    PrivateReplyTable,
    PublicationTable,
)
from src.shared.dates import utc_now


class PublicationRepository(MySQLRepository[PublicationModel]):
    table = PublicationTable

    async def get(
        self, id: int, *, lock: bool = False
    ) -> PublicationModel | None:
        stmt = select(self.table).where(col(self.table.id) == id)
        if lock:
            stmt = stmt.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def by_key(self, key: str) -> PublicationModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.key) == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def day_count(self, day: date) -> int:
        result = await self.uow.execute(
            select(col(self.table.id))
            .where(
                col(self.table.budget_day) == day,
                col(self.table.status).in_(
                    ["reserved", "sending", "sent", "unknown"]
                ),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return len(result.all())

    async def save(self, model: PublicationModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == model.id)
            .values(**model.model_dump(exclude={"id", "created_at"}))
        )

    async def due(
        self, now: datetime, limit: int
    ) -> Sequence[PublicationModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.status) == "queued",
                col(self.table.scheduled_at) <= now,
            )
            .order_by(col(self.table.id))
            .limit(limit)
        )
        return result.scalars().all()

    async def recover_sending(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(
                col(self.table.status) == "sending",
                col(self.table.lease_expires_at) < now,
            )
            .values(status="unknown", failure_reason="dispatch_interrupted")
        )

    async def expire_queued(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(
                col(self.table.status) == "queued",
                col(self.table.deadline) <= now,
            )
            .values(status="expired")
        )


class PrivateReplyRepository(MySQLRepository[PrivateReplyModel]):
    table = PrivateReplyTable

    async def get(self, id: int) -> PrivateReplyModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def due(self, limit: int) -> Sequence[PrivateReplyModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.status) == "queued",
                col(self.table.scheduled_at) <= utc_now(),
            )
            .order_by(col(self.table.id))
            .limit(limit)
        )
        return result.scalars().all()

    async def save(self, model: PrivateReplyModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == model.id)
            .values(**model.model_dump(exclude={"id", "created_at"}))
        )

    async def recover_sending(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(
                col(self.table.status) == "sending",
                col(self.table.lease_expires_at) < now,
            )
            .values(
                status="unknown", failure_reason="reply_delivery_interrupted"
            )
        )
