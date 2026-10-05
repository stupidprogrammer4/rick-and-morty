from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from portal_contracts.enums import BotRole


class ScheduledMissionCreate(BaseModel):
    owner_id: int = Field(gt=0)
    role: BotRole
    intent: Literal["news", "prices", "charts", "occasions"]
    text: str
    scheduled_at: AwareDatetime


class MissionChange(BaseModel):
    status: str
    stage: str
    lease_expires_at: datetime | None = None
    result: str | None = None
    failure_reason: str | None = None


class MissionClaim(BaseModel):
    now: datetime
    lease_expires_at: datetime
    version: int
