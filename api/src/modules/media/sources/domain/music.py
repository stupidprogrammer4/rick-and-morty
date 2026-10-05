from pydantic import BaseModel

from src.modules.media.sources.domain.dtos import DownloadItem


class MusicCandidate(BaseModel):
    url: str
    title: str
    performer: str | None = None
    duration: float | None = None
    isrc: str | None = None


class MusicSearch(BaseModel):
    source: str
    candidates: list[MusicCandidate]
    error: str | None = None


class MusicMatch(BaseModel):
    candidate: MusicCandidate
    score: float


class ResolvedMedia(BaseModel):
    item: DownloadItem
    duration: float
    source: MusicCandidate
