from dishka import Provider, Scope, alias, provide

from src.modules.pricing.bubbles.app.commands import (
    CreateBubble,
    UpdateBubbleConfig,
)
from src.modules.pricing.bubbles.app.queries import GetBubblesWithConfig
from src.modules.pricing.bubbles.app.services import (
    BubbleConfigService,
    BubbleService,
    BubbleSourceService,
)
from src.modules.pricing.bubbles.infra.mysql import (
    BubbleConfigRepository,
    BubbleRepository,
)
from src.modules.pricing.bubbles.infra.readers import BubbleReader
from src.modules.pricing.bubbles.interfaces import (
    IBubbleConfigService,
    IBubbleService,
    IBubbleSourceService,
    ICreateBubble,
    IGetBubblesWithConfig,
    IUpdateBubbleConfig,
)


class BubbleProvider(Provider):
    scope = Scope.REQUEST

    reader = provide(BubbleReader)
    create_bubble = provide(CreateBubble)
    update_config = provide(UpdateBubbleConfig)
    get_with_config = provide(GetBubblesWithConfig)

    bubble_repo = provide(BubbleRepository)
    bubble_config_repo = provide(BubbleConfigRepository)
    bubble_config_service = provide(
        BubbleConfigService, provides=IBubbleConfigService
    )
    bubble_service = provide(BubbleService, provides=IBubbleService)
    bubble_source_service = provide(
        BubbleSourceService, provides=IBubbleSourceService
    )

    create_bubble_contract = alias(CreateBubble, provides=ICreateBubble)

    get_bubbles_with_config_contract = alias(
        GetBubblesWithConfig, provides=IGetBubblesWithConfig
    )

    update_bubble_config_contract = alias(
        UpdateBubbleConfig, provides=IUpdateBubbleConfig
    )
