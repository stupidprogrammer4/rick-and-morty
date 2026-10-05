import asyncio
from collections.abc import Sequence

from papilio.infra.db.transaction import transaction

from src.modules.media.library.app.keys import MediaAssetKeys
from src.modules.media.library.interfaces import IMediaAssetService
from src.modules.media.sources.app.requests import MediaExtractionRequests
from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    MediaDownloadOutcome,
    MediaDownloadSink,
    SourceDownloadInput,
    SourceJob,
)
from src.modules.media.sources.interfaces import IMediaSourceTransfer


class MediaFileDownloads:
    def __init__(
        self,
        requests: MediaExtractionRequests,
        transfer: IMediaSourceTransfer,
        assets: IMediaAssetService,
        keys: MediaAssetKeys,
    ):
        self.requests = requests
        self.transfer = transfer
        self.assets = assets
        self.keys = keys

    async def download(
        self, job: SourceJob, item_id: int, item: DownloadItem
    ) -> DownloadedFile:
        request = self.requests.file(job, item_id, item)
        key = self.keys.key(job, item)
        if key:
            async with transaction():
                cached = await self.assets.get(key)
            if cached is not None:
                return cached
        result = await self.transfer.fetch(request)
        return result.model_copy(update={"cache_key": key})

    async def download_many(
        self,
        inputs: Sequence[SourceDownloadInput],
        completed: MediaDownloadSink,
    ) -> list[MediaDownloadOutcome]:
        lookups = {
            data.item.id: self.keys.key(
                data.job, DownloadItem.model_validate_json(data.item.payload)
            )
            for data in inputs
        }
        async with transaction():
            cached = await self.assets.get_many(
                [key for key in lookups.values() if key]
            )
        available = {row.key: row.downloaded for row in cached}
        prepared = [
            data.model_copy(
                update={"cached": available.get(lookups[data.item.id] or "")}
            )
            for data in inputs
        ]
        responses = await asyncio.gather(
            *(self.receive(data, completed) for data in prepared),
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
            item = DownloadItem.model_validate_json(data.item.payload)
            if data.cached is not None:
                downloaded = data.cached
            else:
                downloaded = await self.transfer.fetch(
                    self.requests.file(data.job, data.item.id, item)
                )
                downloaded = downloaded.model_copy(
                    update={"cache_key": self.keys.key(data.job, item)}
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
