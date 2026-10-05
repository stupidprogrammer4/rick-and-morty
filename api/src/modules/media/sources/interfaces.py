from collections.abc import Awaitable, Sequence
from typing import Protocol

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadPlan,
    DownloadStage,
    MediaDownloadOutcome,
    MediaDownloadSink,
    SourceDownloadInput,
    SourceJob,
)


class IMediaSourcePlanner(Protocol):
    def plan(
        self, job: SourceJob, stages: Sequence[DownloadStage]
    ) -> Awaitable[DownloadPlan]: ...


class IMediaFileDownloads(Protocol):
    def download(
        self, job: SourceJob, item_id: int, item: DownloadItem
    ) -> Awaitable[DownloadedFile]: ...
    def download_many(
        self,
        inputs: Sequence[SourceDownloadInput],
        completed: MediaDownloadSink,
    ) -> Awaitable[list[MediaDownloadOutcome]]: ...
