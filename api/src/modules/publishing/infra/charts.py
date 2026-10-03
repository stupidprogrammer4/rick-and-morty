from collections.abc import Sequence
from datetime import datetime

from papilio.infra.db.repositories.backends.mysql import (
    MySQLReader,
    MySQLRepository,
)
from sqlalchemy import inspect, select, update
from sqlmodel import col

from src.modules.publishing.domain.models import PublicationChartModel
from src.modules.publishing.domain.read_models import ChartParentReadModel
from src.modules.publishing.infra.tables import (
    PublicationChartTable,
    PublicationTable,
)


class PublicationChartRepository(MySQLRepository[PublicationChartModel]):
    table = PublicationChartTable

    async def create_all(self, rows: Sequence[PublicationChartModel]) -> None:
        if rows:
            fields = PublicationChartModel.model_fields.items()
            await self.bulk_insert(
                rows,
                insert_columns={
                    name: inspect(self.table).columns[name]
                    for name, field in fields
                    if field.is_required()
                },
            )

    async def locked(self, id: int) -> PublicationChartModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def save(self, row: PublicationChartModel) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == row.id)
            .execution_options(synchronize_session=False)
            .values(**row.model_dump(exclude={"id", "created_at"}))
        )

    async def recover(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "rendering",
                col(self.table.lease_expires_at) < now,
            )
            .values(status="queued", lease_expires_at=None)
        )
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "sending",
                col(self.table.lease_expires_at) < now,
            )
            .values(
                status="unknown", failure_reason="chart_dispatch_interrupted"
            )
        )
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "queued",
                col(self.table.deadline) <= now,
            )
            .values(status="expired")
        )


class PublicationChartReader(MySQLReader):
    async def parent(self, publication_id: int) -> ChartParentReadModel | None:
        result = await self.uow.execute(
            select(PublicationTable).where(
                col(PublicationTable.id) == publication_id
            )
        )
        row = result.scalar_one_or_none()
        return (
            ChartParentReadModel.model_validate(row, from_attributes=True)
            if row
            else None
        )

    async def due(self, now: datetime, limit: int) -> list[int]:
        result = await self.uow.execute(
            select(col(PublicationChartTable.id))
            .join(
                PublicationTable,
                col(PublicationTable.id)
                == col(PublicationChartTable.publication_id),
            )
            .where(
                col(PublicationChartTable.status) == "queued",
                col(PublicationTable.status) == "sent",
                col(PublicationChartTable.scheduled_at) <= now,
            )
            .order_by(col(PublicationChartTable.id))
            .limit(limit)
        )
        return list(result.scalars())

    async def for_publication(
        self, publication_id: int, owner_id: int
    ) -> list[PublicationChartModel]:
        result = await self.uow.execute(
            select(PublicationChartTable)
            .where(
                col(PublicationChartTable.publication_id) == publication_id,
                col(PublicationChartTable.owner_id) == owner_id,
            )
            .order_by(col(PublicationChartTable.id))
        )
        return list(result.scalars())
