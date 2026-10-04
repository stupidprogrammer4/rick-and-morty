from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import literal, select
from sqlmodel import col

from src.modules.ops.guards.infra.mysql import PortalGuardRepository
from src.modules.pricing.assets.infra.tables import (
    AssetConfigTable,
    AssetTable,
)
from src.modules.pricing.bubbles.infra.tables import (
    BubbleConfigTable,
    BubbleTable,
)
from src.modules.pricing.calculator.domain.context import ScheduleConfig


class ScheduleReader:
    def __init__(self, uow: MySQLUnitOfWork) -> None:
        self.uow = uow

    async def try_lock(self) -> bool:
        """Serialize repair passes until transaction end."""
        await PortalGuardRepository(self.uow).lock("pricing:schedule-repair")
        return True

    async def get_all(self) -> list[ScheduleConfig]:
        """Read both kinds of schedule configuration in one snapshot."""
        assets = select(
            literal("asset").label("kind"),
            col(AssetTable.id).label("id"),
            col(AssetTable.code),
            col(AssetConfigTable.scheduler_on),
            col(AssetConfigTable.scheduler_seconds),
        ).join(
            AssetConfigTable,
            col(AssetConfigTable.asset_id) == col(AssetTable.id),
        )
        bubbles = select(
            literal("bubble").label("kind"),
            col(BubbleTable.id).label("id"),
            col(BubbleTable.code),
            col(BubbleConfigTable.scheduler_on),
            col(BubbleConfigTable.scheduler_seconds),
        ).join(
            BubbleConfigTable,
            col(BubbleConfigTable.bubble_id) == col(BubbleTable.id),
        )
        result = await self.uow.execute(assets.union_all(bubbles))
        return [
            ScheduleConfig.model_validate(row) for row in result.mappings()
        ]
