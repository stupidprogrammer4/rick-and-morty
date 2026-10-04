from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from portal_contracts.media import MediaExtractor, MediaPolicy

DownloadStage = MediaExtractor


class DownloadItem(BaseModel):
    url: str
    title: str = "Media"
    engine: Literal["video", "direct", "spotify"] = "video"
    source_url: str
    kind: Literal["audio", "video", "photo", "document"] = "video"
    performer: str | None = None
    duration: float | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class DownloadPlan(BaseModel):
    items: list[DownloadItem]


class DownloadedFile(BaseModel):
    filename: str
    kind: Literal["audio", "video", "photo", "document"]
    title: str
    source_url: str
    performer: str | None = None


class MediaDownloadOutcome(BaseModel):
    item_id: int
    job_id: int
    lease_until: datetime | None = None
    downloaded: DownloadedFile | None = None
    error: str | None = None


class DownloadProcessRequest(BaseModel):
    operation: Literal["plan", "download"]
    url: str
    provider: str
    mode: Literal["media", "audio"]
    policy: MediaPolicy
    directory: str
    item: DownloadItem | None = None
    cookie_file: str | None = None
    stages: list[DownloadStage] = Field(default_factory=list)


MediaDownloadSink = Callable[[MediaDownloadOutcome], Awaitable[None]]


class SourceJob(BaseModel):
    id: int
    url: str
    provider: str
    mode: Literal["media", "audio"]


class SourceItem(BaseModel):
    id: int
    payload: str
    lease_until: datetime | None = None


class SourceDownloadInput(BaseModel):
    job: SourceJob
    item: SourceItem
