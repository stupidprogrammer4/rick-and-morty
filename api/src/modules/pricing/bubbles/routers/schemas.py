from datetime import datetime

from src.modules.pricing.bubbles.config.constants import (
    BubbleIDField,
)
from src.modules.pricing.bubbles.domain.models import (
    BubbleBase,
    BubbleConfigBase,
)


class BubbleConfigOut(BubbleConfigBase):
    bubble_id: BubbleIDField
    created_at: datetime
    updated_at: datetime


class BubbleOut(BubbleBase):
    id: BubbleIDField
    created_at: datetime
    updated_at: datetime


class BubbleWithConfigOut(BubbleOut):
    config: BubbleConfigOut | None = None
