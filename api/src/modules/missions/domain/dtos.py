from datetime import datetime

from pydantic import BaseModel


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
