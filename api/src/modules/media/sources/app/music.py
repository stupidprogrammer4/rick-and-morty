import asyncio

from src.modules.media.sources.app.matching import MusicMatching
from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.sources.domain.music import (
    MusicMatch,
    MusicSearch,
    ResolvedMedia,
)
from src.modules.media.sources.infra.metadata import MediaMetadataExtraction


class MusicSourceResolver:
    def __init__(
        self, metadata: MediaMetadataExtraction, matching: MusicMatching
    ):
        self.metadata = metadata
        self.matching = matching

    async def search(
        self, request: DownloadProcessRequest, source: str, query: str
    ) -> MusicSearch:
        try:
            candidates = await self.metadata.search(request, source, query)
            return MusicSearch(source=source, candidates=candidates)
        except Exception as exc:
            return MusicSearch(
                source=source, candidates=[], error=type(exc).__name__
            )

    async def candidate(
        self,
        request: DownloadProcessRequest,
        item: DownloadItem,
        match: MusicMatch,
    ) -> ResolvedMedia:
        candidate = match.candidate
        chosen = item.model_copy(
            update={
                "url": candidate.url,
                "source_url": candidate.url,
                "kind": "audio",
            }
        )
        resolved = await self.metadata.resolve(request, chosen)
        if (
            self.matching.score(item, resolved.source)
            < request.policy.music_match_threshold
        ):
            raise ValueError(
                "Resolved audio does not match the requested track"
            )
        return resolved

    async def resolve(
        self, request: DownloadProcessRequest, item: DownloadItem
    ) -> ResolvedMedia:
        query = item.title + " " + (item.performer or "")
        searches = await asyncio.gather(
            *(
                self.search(request, source, query)
                for source in dict.fromkeys(request.policy.music_sources)
            )
        )
        ranked = self.matching.rank(
            item,
            [
                candidate
                for result in searches
                for candidate in result.candidates
            ],
        )
        if not ranked:
            raise ValueError(
                "No public audio matches the track, artist and version"
            )
        resolved = await asyncio.gather(
            *(self.candidate(request, item, match) for match in ranked[:2]),
            return_exceptions=True,
        )
        valid = next(
            (
                result
                for result in resolved
                if isinstance(result, ResolvedMedia)
            ),
            None,
        )
        if valid is None:
            raise ValueError(
                "Matching sources did not expose"
                " a complete compatible audio file"
            )
        return valid
