from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import (
    MySQLPersistenceRepository,
    MySQLRepository,
)
from sqlalchemy import or_, select, update
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from src.modules.media.downloads.domain.dtos import (
    MediaItemChange,
    MediaJobChange,
)
from src.modules.media.downloads.domain.models import (
    MediaItemModel,
    MediaJobModel,
)
from src.modules.media.downloads.infra.tables import (
    MediaItemTable,
    MediaJobTable,
)


class MediaJobRepository(MySQLRepository[MediaJobModel]):
    table = MediaJobTable

    async def get(self, id: int, lock: bool = False) -> MediaJobModel | None:
        statement = (
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(statement)
        return result.scalar_one_or_none()

    async def by_update(
        self, bot_id: int, update_id: int
    ) -> MediaJobModel | None:
        result = await self.uow.execute(
            select(self.table).where(
                col(self.table.bot_id) == bot_id,
                col(self.table.update_id) == update_id,
            )
        )
        return result.scalar_one_or_none()

    async def change(self, id: int, data: MediaJobChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(**data.model_dump(exclude_unset=True))
            .execution_options(synchronize_session=False)
        )

    async def due(self, limit: int, now: datetime) -> Sequence[MediaJobModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.status) == "queued",
                or_(
                    col(self.table.available_at).is_(None),
                    col(self.table.available_at) <= now,
                ),
                or_(
                    col(self.table.lease_until).is_(None),
                    col(self.table.lease_until) <= now,
                ),
            )
            .order_by(col(self.table.id))
            .limit(limit)
            .with_for_update()
        )
        return result.scalars().all()

    async def dispatch_many(
        self, ids: Sequence[int], lease_until: datetime
    ) -> None:
        if ids:
            await self.uow.execute(
                update(self.table)
                .where(col(self.table.id).in_(ids))
                .values(lease_until=lease_until)
                .execution_options(synchronize_session=False)
            )

    async def start_many(self, ids: Sequence[int]) -> None:
        if ids:
            await self.uow.execute(
                update(self.table)
                .where(col(self.table.id).in_(ids))
                .values(status="running", lease_until=None)
                .execution_options(synchronize_session=False)
            )

    async def expired(self, now: datetime) -> Sequence[MediaJobModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.status).in_(["planning", "running"]),
                col(self.table.lease_until) <= now,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()

    async def requeue_many(self, ids: Sequence[int]) -> None:
        if ids:
            await self.uow.execute(
                update(self.table)
                .where(col(self.table.id).in_(ids))
                .values(status="queued", lease_until=None)
                .execution_options(synchronize_session=False)
            )


class MediaItemRepository(MySQLPersistenceRepository[MediaItemModel]):
    table = MediaItemTable

    async def insert_items(self, rows: Sequence[MediaItemModel]) -> None:
        if rows:
            from sqlalchemy.dialects.mysql import insert

            await self.uow.execute(
                insert(self.table).values([row.to_row() for row in rows])
            )

    async def get(self, id: int, lock: bool = False) -> MediaItemModel | None:
        statement = (
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        result = await self.uow.execute(statement)
        return result.scalar_one_or_none()

    async def next_delivery(self, job_id: int) -> MediaItemModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.job_id) == job_id,
                col(self.table.status).in_(
                    ["queued", "reserved", "downloading", "ready", "sending"]
                ),
            )
            .order_by(col(self.table.position))
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def ready(self, job_id: int) -> MediaItemModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.job_id) == job_id,
                col(self.table.status) == "ready",
            )
            .order_by(col(self.table.position))
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def reserve_many(
        self, ids: Sequence[int], lease_until: datetime
    ) -> None:
        if ids:
            await self.uow.execute(
                update(self.table)
                .where(col(self.table.id).in_(ids))
                .values(status="reserved", lease_until=lease_until)
                .execution_options(synchronize_session=False)
            )

    async def recover(self, now: datetime) -> None:
        expired = or_(
            col(self.table.lease_until).is_(None),
            col(self.table.lease_until) <= now,
        )
        await self.uow.execute(
            update(self.table)
            .where(expired, col(self.table.status) == "sending")
            .values(
                status="unknown",
                lease_until=None,
                error="Delivery interrupted; not replayed automatically",
            )
            .execution_options(synchronize_session=False)
        )

        await self.uow.execute(
            update(self.table)
            .where(
                expired,
                col(self.table.status).in_(["reserved", "downloading"]),
            )
            .values(status="queued", filename=None, lease_until=None)
            .execution_options(synchronize_session=False)
        )

    async def save_many(self, rows: Sequence[MediaItemModel]) -> None:
        if rows:
            await self.bulk_update(
                rows,
                update_columns={
                    "status": cast(ColumnClause[Any], col(self.table.status)),
                    "lease_until": cast(
                        ColumnClause[Any], col(self.table.lease_until)
                    ),
                    "available_at": cast(
                        ColumnClause[Any], col(self.table.available_at)
                    ),
                    "filename": cast(
                        ColumnClause[Any], col(self.table.filename)
                    ),
                    "downloaded_payload": cast(
                        ColumnClause[Any], col(self.table.downloaded_payload)
                    ),
                    "source_url": cast(
                        ColumnClause[Any], col(self.table.source_url)
                    ),
                    "error": cast(ColumnClause[Any], col(self.table.error)),
                },
            )

    async def next(self, job_id: int) -> MediaItemModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.job_id) == job_id,
                col(self.table.status) == "queued",
            )
            .order_by(col(self.table.position))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def change(self, id: int, data: MediaItemChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(**data.model_dump(exclude_unset=True))
            .execution_options(synchronize_session=False)
        )

    async def interrupt(self, job_id: int) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.job_id) == job_id,
                col(self.table.status) == "sending",
            )
            .values(
                status="unknown",
                error="Delivery interrupted; not replayed automatically",
            )
            .execution_options(synchronize_session=False)
        )
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.job_id) == job_id,
                col(self.table.status) == "downloading",
            )
            .values(status="queued", filename=None)
            .execution_options(synchronize_session=False)
        )

    async def interrupt_many(self, ids: Sequence[int]) -> None:
        if not ids:
            return
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.job_id).in_(ids),
                col(self.table.status) == "sending",
            )
            .values(
                status="unknown",
                error="Delivery interrupted; not replayed automatically",
            )
            .execution_options(synchronize_session=False)
        )
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.job_id).in_(ids),
                col(self.table.status) == "downloading",
            )
            .values(status="queued", filename=None)
            .execution_options(synchronize_session=False)
        )
