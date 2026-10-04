from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class QueueStatus(BaseModel):
    queued_charts: int
    unknown_charts: int
    queued_missions: int
    running_missions: int
    queued_publications: int
    unknown_publications: int
    unknown_private_replies: int
    oldest_queued_mission: datetime | None
    ai_reserved_usd: Decimal


class PortalStatus(BaseModel):
    database: bool
    paused: bool
    dry_run: bool
    ai_mode: str
    model_configured: bool
    market_enabled: bool
    daily_post_cap: int
    queues: QueueStatus


class TaskStreams(BaseModel):
    main: str
    media: str
