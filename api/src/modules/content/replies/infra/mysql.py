from collections.abc import Sequence
from datetime import datetime

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlmodel import col

from src.modules.content.replies.domain.models import PrivateReplyModel
from src.modules.content.replies.infra.tables import PrivateReplyTable
from src.shared.dates import utc_now


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
