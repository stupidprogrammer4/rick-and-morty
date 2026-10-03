from papilio.infra.db.table import BaseTable
from sqlalchemy import Column, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlmodel import Field

from src.modules.rick.domain.models import (
    AgentCheckpointModel,
    AIBudgetModel,
    LLMRunModel,
)


class AgentCheckpointTable(AgentCheckpointModel, BaseTable, table=True):
    history: str = Field(
        sa_column=Column(
            Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False
        )
    )


class AIBudgetTable(AIBudgetModel, BaseTable, table=True):
    pass


class LLMRunTable(LLMRunModel, BaseTable, table=True):
    __table_args__ = (UniqueConstraint("mission_id", "request_no"),)
