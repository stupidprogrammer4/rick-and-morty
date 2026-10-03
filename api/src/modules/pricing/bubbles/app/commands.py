from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional

from src.modules.pricing.bubbles.domain.dtos import (
    BubbleConfigUpdate,
    BubbleCreate,
)
from src.modules.pricing.bubbles.domain.models import (
    BubbleConfigModel,
    BubbleModel,
)
from src.modules.pricing.bubbles.interfaces import (
    IBubbleConfigService,
    IBubbleService,
)
from src.modules.pricing.calculator.interfaces import IBubbleSchedulerService


class CreateBubble:
    def __init__(
        self, bubbles: IBubbleService, configs: IBubbleConfigService
    ) -> None:
        self.bubbles = bubbles
        self.configs = configs

    @handle_conflicts
    @transactional
    async def execute(self, data: BubbleCreate) -> BubbleModel:
        """Create the bubble and its default config atomically."""
        bubble = await self.bubbles.create(data)
        await self.configs.create_default(bubble.id)
        return bubble


class UpdateBubbleConfig:
    def __init__(
        self, configs: IBubbleConfigService, scheduler: IBubbleSchedulerService
    ) -> None:
        self.configs = configs
        self.scheduler = scheduler

    @handle_conflicts
    @transactional
    async def execute(
        self, bubble_id: int, data: BubbleConfigUpdate
    ) -> BubbleConfigModel:
        """Update config and synchronize its schedule when requested."""
        config = await self.configs.update(bubble_id, data)
        if data.scheduler_on is not None or data.scheduler_seconds is not None:
            await self.scheduler.sync(
                bubble_id, config.scheduler_on, config.scheduler_seconds
            )
        return config
