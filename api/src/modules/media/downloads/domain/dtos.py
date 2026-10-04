from datetime import datetime

from pydantic import BaseModel

from src.modules.media.downloads.domain.models import (
    MediaItemModel,
    MediaJobModel,
)


class MediaDownloadInput(BaseModel):
    job: MediaJobModel
    item: MediaItemModel


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
