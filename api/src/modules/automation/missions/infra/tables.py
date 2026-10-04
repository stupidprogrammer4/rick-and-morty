from papilio.infra.db.table import BaseTable
from sqlalchemy import Index, UniqueConstraint

from src.modules.automation.missions.domain.models import (
    MissionEventModel,
    MissionModel,
)


class MissionTable(MissionModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("bot_id", "update_id"),
        UniqueConstraint("automation_key", name="uq_missions_automation_key"),
        Index("ix_missions_due", "status", "id"),
        Index("ix_missions_owner_status", "owner_id", "status"),
    )


class MissionEventTable(MissionEventModel, BaseTable, table=True):
    pass
