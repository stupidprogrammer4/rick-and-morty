from datetime import date
from decimal import Decimal

from papilio.infra.db.schema.entity import BaseEntity, PersistenceEntity
from papilio.infra.db.schema.fields import (
    CharField,
    DateField,
    ForeignKeyField,
    IntField,
    NumericField,
    TextField,
)


class AgentCheckpointModel(BaseEntity):
    mission_id: int = ForeignKeyField("tbl_missions.id", primary_key=True)
    history: str = TextField()
    requests: int = IntField(default=0)
    tools: int = IntField(default=0)
    reactions: int = IntField(default=0)
    input_tokens: int = IntField(default=0)


class AIBudgetModel(BaseEntity):
    day: date = DateField(primary_key=True)
    reserved_usd: Decimal = NumericField(18, 8, default=Decimal("0"))


class LLMRunModel(PersistenceEntity):
    mission_id: int = ForeignKeyField("tbl_missions.id", index=True)
    request_no: int = IntField()
    budget_day: date = DateField()
    reserved_usd: Decimal = NumericField(18, 8)
    actual_usd: Decimal | None = NumericField(
        18, 8, default=None, nullable=True
    )
    status: str = CharField(16, default="reserved")
    input_tokens: int = IntField(default=0)
    output_tokens: int = IntField(default=0)
