from collections.abc import Sequence
from datetime import datetime

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert
from sqlmodel import col

from src.modules.media.library.domain.models import MediaAssetModel
from src.modules.media.library.infra.tables import MediaAssetTable


class MediaAssetRepository(MySQLRepository[MediaAssetModel]):
    table = MediaAssetTable

    async def get(self, key: str, now: datetime) -> MediaAssetModel | None:
        result = await self.uow.execute(
            select(self.table).where(
                col(self.table.cache_key) == key,
                col(self.table.expires_at) > now,
            )
        )
        return result.scalar_one_or_none()

    async def get_many(
        self, keys: Sequence[str], now: datetime
    ) -> Sequence[MediaAssetModel]:
        if not keys:
            return []
        result = await self.uow.execute(
            select(self.table).where(
                col(self.table.cache_key).in_(keys),
                col(self.table.expires_at) > now,
            )
        )
        return result.scalars().all()

    async def store(self, data: MediaAssetModel) -> None:
        statement = insert(self.table).values(data.to_row())
        await self.uow.execute(
            statement.on_duplicate_key_update(
                file_id=statement.inserted.file_id,
                payload=statement.inserted.payload,
                expires_at=statement.inserted.expires_at,
            )
        )

    async def invalidate(self, key: str) -> None:
        await self.uow.execute(
            delete(self.table).where(col(self.table.cache_key) == key)
        )

    async def prune(self, now: datetime) -> None:
        await self.uow.execute(
            delete(self.table).where(col(self.table.expires_at) <= now)
        )
