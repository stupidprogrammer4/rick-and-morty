from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from portal_contracts.media import MediaExtractor, MediaPolicy
from src.modules.media.domain.models import MediaItemModel, MediaJobModel

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


class MediaDownloadInput(BaseModel):
    job: MediaJobModel
    item: MediaItemModel


class MediaDownloadOutcome(BaseModel):
    item_id: int
    job_id: int
    lease_until: datetime | None = None
    downloaded: DownloadedFile | None = None
    error: str | None = None


MediaDownloadSink = Callable[[MediaDownloadOutcome], Awaitable[None]]


class MediaDiskUsage(BaseModel):
    used_bytes: int
    free_bytes: int


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


class MediaJobChange(BaseModel):
    status: str
    lease_until: datetime | None = None
    available_at: datetime | None = None
    total: int | None = None
    sent: int | None = None
    failed: int | None = None
    error: str | None = None


class MediaItemChange(BaseModel):
    status: str
    filename: str | None = None
    message_id: int | None = None
    file_id: str | None = None
    source_url: str | None = None
    error: str | None = None
    lease_until: datetime | None = None
    available_at: datetime | None = None
    downloaded_payload: str | None = None
