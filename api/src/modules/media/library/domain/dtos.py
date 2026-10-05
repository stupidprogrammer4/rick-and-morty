from pydantic import BaseModel

from src.modules.media.sources.domain.dtos import DownloadedFile


class MediaCacheEntry(BaseModel):
    key: str
    downloaded: DownloadedFile
