from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional

from src.modules.pricing.sources.domain.dtos import SourceCreate
from src.modules.pricing.sources.domain.models import SourceModel
from src.modules.pricing.sources.interfaces import (
    ISourceConfigService,
    ISourceService,
)


class CreateSource:
    def __init__(
        self, sources: ISourceService, configs: ISourceConfigService
    ) -> None:
        self.sources = sources
        self.configs = configs

    @handle_conflicts
    @transactional
    async def execute(self, data: SourceCreate) -> SourceModel:
        """Create the source and its default config atomically."""
        source = await self.sources.create(data)
        await self.configs.create_default(source.id)
        return source
