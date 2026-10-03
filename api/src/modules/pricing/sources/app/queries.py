from typing import Sequence

from papilio.schemas.results import PagedType

from src.modules.pricing.sources.config.constants import SOURCE_ID_ENCRYPTION
from src.modules.pricing.sources.domain.dtos import SourceSearch
from src.modules.pricing.sources.domain.enums import SourceSwitch
from src.modules.pricing.sources.domain.models import (
    SourceModel,
    SourceWithConfigModel,
)
from src.modules.pricing.sources.infra.readers import SourceReader


class SearchSources:
    def __init__(self, reader: SourceReader) -> None:
        self.reader = reader

    async def execute(self, data: SourceSearch) -> PagedType[SourceModel]:
        """
        Desc: Get a filtered page of sources.
        Args:
            data (SourceSearch): Free text, market filters and paging.
        Returns:
            return (PagedType[SourceModel]): The page and the total count.
        """
        id_match = None
        if data.q is not None and data.q.isdigit():
            id_match = SOURCE_ID_ENCRYPTION.try_decode(int(data.q))
        paged = await self.reader.search(
            q=data.q,
            source_types=data.source_types,
            update_types=data.update_types,
            is_active=data.is_active,
            has_error=data.has_error,
            sort_by=data.sort_by,
            sort_order=data.sort_order,
            offset=(data.page - 1) * data.per_page,
            limit=data.per_page,
            id_match=id_match,
        )
        return paged


class GetSourcesWithConfig:
    def __init__(self, reader: SourceReader) -> None:
        self.reader = reader

    async def execute(
        self, switch: SourceSwitch | None = None
    ) -> Sequence[SourceWithConfigModel]:
        sources = await self.reader.get_with_config(switch=switch)
        return sources
