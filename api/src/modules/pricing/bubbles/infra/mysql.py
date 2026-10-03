from collections.abc import Sequence
from typing import Any, Optional

from papilio.infra.db.repositories.backends.mysql import (
    MySQLIdentifiedRepository,
    MySQLTimestampRepository,
)
from sqlalchemy import update
from sqlmodel import col, select

from src.modules.pricing.bubbles.domain.models import (
    BubbleConfigModel,
    BubbleModel,
)
from src.modules.pricing.bubbles.infra.tables import (
    BubbleConfigTable,
    BubbleTable,
)


class BubbleRepository(MySQLIdentifiedRepository[BubbleModel]):
    table = BubbleTable

    async def get_by_id(self, id: int) -> BubbleModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()


class BubbleConfigRepository(MySQLTimestampRepository[BubbleConfigModel]):
    table = BubbleConfigTable

    async def bulk_create(
        self, data: Sequence[BubbleConfigModel]
    ) -> Sequence[BubbleConfigModel]:
        records = [self.table(**row.to_row()) for row in data]
        self.uow.session.add_all(records)
        await self.uow.flush()
        return records

    async def get_by_bubble_id(
        self,
        bubble_id: int,
    ) -> Optional[BubbleConfigModel]:
        """
        Desc: Get a bubble's config by the bubble it belongs to.
        Args:
            bubble_id (int): ID of the owning bubble.
        Returns:
            return (Optional[BubbleConfigModel]): Found config or None.
        """
        stmt = select(BubbleConfigTable).where(
            col(BubbleConfigTable.bubble_id) == bubble_id
        )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def update_by_bubble_id(
        self,
        bubble_id: int,
        row: dict[str, Any],
    ) -> Optional[BubbleConfigModel]:
        """
        Desc: Patch a bubble's config from a column dict.
        Args:
            bubble_id (int): ID of the owning bubble.
            row (dict[str, Any]): Column values to write.
        Returns:
            return (Optional[BubbleConfigModel]): Updated config or None.
        """
        await self.uow.execute(
            update(BubbleConfigTable)
            .where(col(BubbleConfigTable.bubble_id) == bubble_id)
            .values(**row)
            .execution_options(synchronize_session=False)
        )
        saved = await self.get_by_bubble_id(bubble_id)
        return saved
