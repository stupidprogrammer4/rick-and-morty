from papilio.errors.exceptions import NotFoundException

from portal_contracts.media import (
    MediaFileDelivery,
    MediaItemPage,
    MediaJobPage,
)
from src.modules.media.downloads.infra.readers import MediaReader
from src.modules.media.downloads.interfaces import (
    IMediaItemService,
    IMediaJobService,
)
from src.modules.media.sources.domain.dtos import DownloadedFile


class MediaQueries:
    def __init__(
        self,
        reader: MediaReader,
        jobs: IMediaJobService,
        items: IMediaItemService,
    ):
        self.reader = reader
        self.jobs = jobs
        self.item_service = items

    async def page(
        self, owner_id: int, page: int, per_page: int
    ) -> MediaJobPage:
        result = await self.reader.jobs(owner_id, page, per_page)
        return result

    async def items(
        self, id: int, owner_id: int, page: int, per_page: int
    ) -> MediaItemPage:
        await self.jobs.get(id, owner_id)
        result = await self.reader.items(id, page, per_page)
        return result

    async def authorize_file(self, data: MediaFileDelivery) -> bool:
        try:
            job = await self.jobs.get(data.job_id, data.owner_id)
            item = await self.item_service.get(data.item_id)
        except NotFoundException:
            return False
        allowed = (
            job.status == "running"
            and item.job_id == job.id
            and item.status == "sending"
            and item.filename == data.filename
        )
        if not allowed:
            return False
        downloaded = DownloadedFile.model_validate_json(
            item.downloaded_payload or ""
        )
        return downloaded.file_id == data.file_id
