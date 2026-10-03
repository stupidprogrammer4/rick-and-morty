from typing import Sequence

from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy.orm import joinedload
from sqlmodel import col, select

from src.modules.pricing.assets.domain.models import AssetWithConfigModel
from src.modules.pricing.assets.infra.tables import AssetTable


class AssetReader:
    def __init__(self, uow: MySQLUnitOfWork) -> None:
        self.uow = uow

    async def get_all_with_config(self) -> Sequence[AssetWithConfigModel]:
        """Read assets with configs in ID order."""
        stmt = (
            select(AssetTable)
            .options(joinedload(AssetTable.config, innerjoin=True))
            .order_by(col(AssetTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = [
            AssetWithConfigModel(**row.to_dict(), config=row.config)
            for row in result.unique().scalars().all()
        ]
        return rows
