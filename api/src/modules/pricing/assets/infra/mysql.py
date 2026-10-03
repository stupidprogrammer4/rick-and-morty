from collections.abc import Sequence
from typing import Any

from papilio.infra.db.repositories.backends.mysql import (
    MySQLIdentifiedRepository,
    MySQLTimestampRepository,
)
from sqlalchemy import case, delete, update
from sqlmodel import col, select

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.domain.models import (
    AssetConfigModel,
    AssetModel,
    AssetSwitchModel,
)
from src.modules.pricing.assets.infra.tables import (
    AssetConfigTable,
    AssetSwitchTable,
    AssetTable,
)


class AssetRepository(MySQLIdentifiedRepository[AssetModel]):
    table = AssetTable

    async def get_by_id(self, id: int) -> AssetModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: AssetCode) -> AssetModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.code) == code)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_code_by_id(self, id: int) -> str | None:
        result = await self.uow.execute(
            select(col(self.table.code)).where(col(self.table.id) == id)
        )
        return result.scalar_one_or_none()


class AssetConfigRepository(MySQLTimestampRepository[AssetConfigModel]):
    table = AssetConfigTable

    async def bulk_create(
        self, data: Sequence[AssetConfigModel]
    ) -> Sequence[AssetConfigModel]:
        records = [self.table(**row.to_row()) for row in data]
        self.uow.session.add_all(records)
        await self.uow.flush()
        return records

    async def get_by_asset_id(self, asset_id: int) -> AssetConfigModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.asset_id) == asset_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def update_by_asset_id(
        self, asset_id: int, row: dict[str, Any]
    ) -> AssetConfigModel | None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.asset_id) == asset_id)
            .values(**row)
            .execution_options(synchronize_session=False)
        )
        result = await self.get_by_asset_id(asset_id)
        return result


class AssetSwitchRepository(MySQLIdentifiedRepository[AssetSwitchModel]):
    table = AssetSwitchTable

    async def bulk_create(
        self, data: Sequence[AssetSwitchModel]
    ) -> Sequence[AssetSwitchModel]:
        records = [self.table(**row.to_row()) for row in data]
        self.uow.session.add_all(records)
        await self.uow.flush()
        return records

    async def update_priorities(
        self, asset_id: int, rows: Sequence[AssetSwitchModel]
    ) -> Sequence[AssetSwitchModel]:
        if not rows:
            return []
        assignments = {row.switch: row.priority for row in rows}
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.asset_id) == asset_id,
                col(self.table.switch).in_(assignments),
            )
            .values(priority=case(assignments, value=col(self.table.switch)))
            .execution_options(synchronize_session=False)
        )
        saved = await self.get_by_asset_id(asset_id)
        return [row for row in saved if row.switch in assignments]

    async def update_by_asset_and_id(
        self, asset_id: int, id: int, row: dict[str, Any]
    ) -> AssetSwitchModel | None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.asset_id) == asset_id, col(self.table.id) == id
            )
            .values(**row)
            .execution_options(synchronize_session=False)
        )
        saved = await self.get_by_id(id)
        return saved if saved and saved.asset_id == asset_id else None

    async def delete_by_asset_and_id(
        self, asset_id: int, id: int
    ) -> AssetSwitchModel | None:
        rows = await self.delete_by_asset_and_ids(asset_id, [id])
        return next(iter(rows), None)

    async def delete_by_asset_and_ids(
        self, asset_id: int, ids: Sequence[int]
    ) -> Sequence[AssetSwitchModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.asset_id) == asset_id,
                col(self.table.id).in_(ids),
            )
            .with_for_update()
        )
        rows = result.scalars().all()
        snapshots = [
            AssetSwitchModel.model_validate(row).model_copy() for row in rows
        ]
        await self.uow.execute(
            delete(self.table)
            .where(
                col(self.table.asset_id) == asset_id,
                col(self.table.id).in_(ids),
            )
            .execution_options(synchronize_session=False)
        )
        return snapshots

    async def get_by_asset_id(
        self, asset_id: int
    ) -> Sequence[AssetSwitchModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.asset_id) == asset_id)
            .order_by(col(self.table.priority))
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()
