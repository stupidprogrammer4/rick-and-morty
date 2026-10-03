from typing import Any, Mapping, Optional, Sequence

from papilio.infra.db.repositories.backends.mysql import (
    MySQLIdentifiedRepository,
    MySQLTimestampRepository,
)
from sqlalchemy import inspect, update
from sqlmodel import col, select

from src.modules.pricing.sources.domain.models import (
    SourceConfigModel,
    SourceModel,
)
from src.modules.pricing.sources.infra.tables import (
    SourceConfigTable,
    SourceTable,
)


class SourceRepository(MySQLIdentifiedRepository[SourceModel]):
    table = SourceTable

    async def get_by_id(self, id: int) -> SourceModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def clear_error(self, id: int) -> SourceModel | None:
        statement = (
            select(SourceTable)
            .where(col(SourceTable.id) == id)
            .with_for_update()
        )
        result = await self.uow.execute(statement)
        source = result.scalar_one_or_none()
        if source is None:
            return None
        previous = SourceModel.model_validate(source).model_copy(deep=True)
        await self.update_by_id(id, SourceModel.patch(error=None).to_row())
        return previous

    async def update_errors(
        self, rows: Sequence[SourceModel]
    ) -> Sequence[SourceModel]:
        """Update source error fields in one statement."""
        if not rows:
            return []
        await self.bulk_update(
            rows, update_columns={"error": inspect(SourceTable).columns.error}
        )
        saved = await self.get_by_ids([row.id for row in rows])
        return saved


class SourceConfigRepository(MySQLTimestampRepository[SourceConfigModel]):
    table = SourceConfigTable

    async def bulk_create(
        self, data: Sequence[SourceConfigModel]
    ) -> Sequence[SourceConfigModel]:
        records = [self.table(**row.to_row()) for row in data]
        self.uow.session.add_all(records)
        await self.uow.flush()
        return records

    async def update_headers_credentials(
        self, credentials: Mapping[int, dict[str, str]]
    ) -> Sequence[SourceConfigModel]:
        """Update only credential headers, matched by source ID."""
        if not credentials:
            return []
        grid = self._values_grid(
            [
                {"source_id": id, "headers_credentials": headers}
                for id, headers in credentials.items()
            ],
            columns={
                "source_id": inspect(SourceConfigTable).columns.source_id,
                "headers_credentials": inspect(
                    SourceConfigTable
                ).columns.headers_credentials,
            },
        )
        await self.uow.execute(
            update(SourceConfigTable)
            .where(col(SourceConfigTable.source_id) == grid.c.source_id)
            .values(headers_credentials=grid.c.headers_credentials)
            .execution_options(synchronize_session=False)
        )
        result = await self.uow.execute(
            select(SourceConfigTable)
            .where(col(SourceConfigTable.source_id).in_(credentials))
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()

    async def get_by_source_id(
        self,
        source_id: int,
    ) -> Optional[SourceConfigModel]:
        """
        Desc: Get a source's config by the source it belongs to.
        Args:
            source_id (int): ID of the owning source.
        Returns:
            return (Optional[SourceConfigModel]): Found config or None.
        """
        stmt = select(SourceConfigTable).where(
            col(SourceConfigTable.source_id) == source_id
        )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def update_by_source_id(
        self,
        source_id: int,
        row: dict[str, Any],
    ) -> Optional[SourceConfigModel]:
        """
        Desc: Patch a source's config from a column dict.
        Args:
            source_id (int): ID of the owning source.
            row (dict[str, Any]): Column values to write.
        Returns:
            return (Optional[SourceConfigModel]): Updated config or None.
        """
        await self.uow.execute(
            update(SourceConfigTable)
            .where(col(SourceConfigTable.source_id) == source_id)
            .values(**row)
            .execution_options(synchronize_session=False)
        )
        saved = await self.get_by_source_id(source_id)
        return saved
