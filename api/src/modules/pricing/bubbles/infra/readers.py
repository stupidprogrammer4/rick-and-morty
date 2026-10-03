from typing import Sequence

from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy.orm import joinedload
from sqlmodel import col, select

from src.modules.pricing.bubbles.domain.models import BubbleWithConfigModel
from src.modules.pricing.bubbles.infra.tables import BubbleTable


class BubbleReader:
    def __init__(self, uow: MySQLUnitOfWork) -> None:
        self.uow = uow

    async def get_all_with_config(self) -> Sequence[BubbleWithConfigModel]:
        """Read bubbles with configs in ID order."""
        stmt = (
            select(BubbleTable)
            .options(joinedload(BubbleTable.config, innerjoin=True))
            .order_by(col(BubbleTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = [
            BubbleWithConfigModel(**row.to_dict(), config=row.config)
            for row in result.unique().scalars().all()
        ]
        return rows
