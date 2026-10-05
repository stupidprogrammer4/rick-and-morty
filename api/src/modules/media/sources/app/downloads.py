import asyncio
from collections.abc import Sequence

from src.modules.media.sources.app.requests import MediaExtractionRequests
from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    MediaDownloadOutcome,
    MediaDownloadSink,
    SourceDownloadInput,
    SourceJob,
)
from src.modules.media.sources.infra.transfer import MediaFileTransfer


class MediaFileDownloads:
    def __init__(
        self, requests: MediaExtractionRequests, transfer: MediaFileTransfer
    ):
        self.requests = requests
        self.transfer = transfer

    async def download(
        self, job: SourceJob, item_id: int, item: DownloadItem
    ) -> DownloadedFile:
        request = self.requests.file(job, item_id, item)
        result = await self.transfer.fetch(request)
        return result

    async def download_many(
        self,
        inputs: Sequence[SourceDownloadInput],
        completed: MediaDownloadSink,
    ) -> list[MediaDownloadOutcome]:
        responses = await asyncio.gather(
            *(self.receive(data, completed) for data in inputs),
            return_exceptions=True,
        )
        if any(isinstance(response, BaseException) for response in responses):
            raise ValueError("Unable to publish one or more download results")
        return [
            response
            for response in responses
            if isinstance(response, MediaDownloadOutcome)
        ]

    async def receive(
        self, data: SourceDownloadInput, completed: MediaDownloadSink
    ) -> MediaDownloadOutcome:
        try:
            downloaded = await self.transfer.fetch(
                self.requests.file(
                    data.job,
                    data.item.id,
                    DownloadItem.model_validate_json(data.item.payload),
                )
            )
        except Exception as exc:
            outcome = self.outcome(data, exc)
        else:
            outcome = self.outcome(data, downloaded)
        await completed(outcome)
        return outcome

    def outcome(
        self,
        data: SourceDownloadInput,
        response: DownloadedFile | BaseException,
    ) -> MediaDownloadOutcome:
        if isinstance(response, BaseException):
            return MediaDownloadOutcome(
                item_id=data.item.id,
                job_id=data.job.id,
                lease_until=data.item.lease_until,
                error=type(response).__name__ + ": " + str(response)[:350],
            )
        return MediaDownloadOutcome(
            item_id=data.item.id,
            job_id=data.job.id,
            lease_until=data.item.lease_until,
            downloaded=response,
        )
