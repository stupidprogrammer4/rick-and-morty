from datetime import datetime

from pydantic import BaseModel, Field

from portal_contracts.enums import Actor, BotRole, Intent


class MissionCreate(BaseModel):
    owner_id: int = Field(gt=0)
    origin_chat_id: int = Field(gt=0)
    origin_bot: BotRole
    origin_message_id: int = Field(gt=0)
    bot_id: int = Field(gt=0)
    update_id: int = Field(ge=0)
    actor: Actor
    intent: Intent
    text: str = Field(min_length=1, max_length=4000)


class MissionOut(BaseModel):
    id: int
    owner_id: int
    origin_bot: BotRole
    actor: Actor
    intent: Intent
    status: str
    stage: str
    created_at: datetime
    deadline: datetime
    result: str | None = None
    failure_reason: str | None = None


class MissionAccepted(BaseModel):
    mission: MissionOut
    duplicate: bool = False


class PageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class MissionPage(BaseModel):
    items: list[MissionOut]
    total: int
    page: int
    per_page: int
