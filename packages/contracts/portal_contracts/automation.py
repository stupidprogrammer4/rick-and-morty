from datetime import datetime

from pydantic import BaseModel

from portal_contracts.enums import Actor, BotRole, Intent


class AgentRequest(BaseModel):
    id: int
    owner_id: int
    actor: Actor
    origin_bot: BotRole
    intent: Intent
    text: str
    automation_key: str | None = None
    deadline: datetime


class AgentOutcome(BaseModel):
    waiting: bool = False
    text: str | None = None
    draft_id: int | None = None
    revision: int | None = None
