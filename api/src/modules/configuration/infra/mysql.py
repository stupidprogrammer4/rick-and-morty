from collections.abc import Sequence

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert
from sqlmodel import col

from portal_contracts.configuration import SettingKey, SettingScope
from src.modules.configuration.domain.models import (
    NewsSourceConfigModel,
    NewsSourceModel,
    SettingDefinitionModel,
    SettingValueModel,
)
from src.modules.configuration.infra.tables import (
    NewsSourceConfigTable,
    NewsSourceTable,
    SettingDefinitionTable,
    SettingValueTable,
)


class SettingDefinitionRepository(MySQLRepository[SettingDefinitionModel]):
    table = SettingDefinitionTable

    async def by_key(self, key: SettingKey) -> SettingDefinitionModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.key) == key)
        )
        return result.scalar_one_or_none()

    async def all(self) -> Sequence[SettingDefinitionModel]:
        result = await self.uow.execute(
            select(self.table).order_by(col(self.table.id))
        )
        return result.scalars().all()

    async def seed_many(self, rows: Sequence[SettingDefinitionModel]) -> None:
        if not rows:
            return
        stmt = insert(self.table).values([row.to_row() for row in rows])
        await self.uow.execute(
            stmt.on_duplicate_key_update(key=stmt.inserted.key)
        )


class SettingValueRepository(MySQLRepository[SettingValueModel]):
    table = SettingValueTable

    async def get(
        self, definition_id: int, scope: SettingScope, lock: bool = False
    ) -> SettingValueModel | None:
        stmt = select(self.table).where(
            col(self.table.definition_id) == definition_id,
            col(self.table.scope) == scope,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, row: SettingValueModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == row.id)
            .values(value=row.value, revision=row.revision)
        )

    async def seed_many(self, rows: Sequence[SettingValueModel]) -> None:
        if not rows:
            return
        stmt = insert(self.table).values([row.to_row() for row in rows])
        await self.uow.execute(
            stmt.on_duplicate_key_update(
                definition_id=stmt.inserted.definition_id
            )
        )


class NewsSourceRepository(MySQLRepository[NewsSourceModel]):
    table = NewsSourceTable

    async def get(self, id: int, lock: bool = False) -> NewsSourceModel | None:
        stmt = select(self.table).where(col(self.table.id) == id)
        if lock:
            stmt = stmt.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def all(self) -> Sequence[NewsSourceModel]:
        result = await self.uow.execute(
            select(self.table).order_by(col(self.table.id))
        )
        return result.scalars().all()

    async def save(self, row: NewsSourceModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == row.id)
            .values(
                title=row.title,
                feed_url=row.feed_url,
                enabled=row.enabled,
                revision=row.revision,
            )
        )

    async def seed_many(self, rows: Sequence[NewsSourceModel]) -> None:
        if not rows:
            return
        stmt = insert(self.table).values([row.to_row() for row in rows])
        await self.uow.execute(
            stmt.on_duplicate_key_update(code=stmt.inserted.code)
        )


class NewsSourceConfigRepository(MySQLRepository[NewsSourceConfigModel]):
    table = NewsSourceConfigTable

    async def get(
        self, source_id: int, lock: bool = False
    ) -> NewsSourceConfigModel | None:
        stmt = select(self.table).where(col(self.table.source_id) == source_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, row: NewsSourceConfigModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.source_id) == row.source_id)
            .values(value=row.value, revision=row.revision)
        )

    async def seed_many(self, rows: Sequence[NewsSourceConfigModel]) -> None:
        if not rows:
            return
        stmt = insert(self.table).values([row.to_row() for row in rows])
        await self.uow.execute(
            stmt.on_duplicate_key_update(source_id=stmt.inserted.source_id)
        )
