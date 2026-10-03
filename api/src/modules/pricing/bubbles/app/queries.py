from typing import Sequence

from src.modules.pricing.bubbles.domain.models import BubbleWithConfigModel
from src.modules.pricing.bubbles.infra.readers import BubbleReader


class GetBubblesWithConfig:
    def __init__(self, reader: BubbleReader) -> None:
        self.reader = reader

    async def execute(self) -> Sequence[BubbleWithConfigModel]:
        bubbles = await self.reader.get_all_with_config()
        return bubbles
