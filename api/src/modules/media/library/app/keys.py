import hashlib
import json

from portal_contracts.media import MediaPolicy
from src.modules.media.sources.domain.dtos import DownloadItem, SourceJob


class MediaAssetKeys:
    def __init__(self, policy: MediaPolicy):
        self.policy = policy

    def key(self, job: SourceJob, item: DownloadItem) -> str | None:
        if (
            not job.bot_id
            or not self.policy.file_cache_seconds
            or item.engine not in {"spotify", "youtube"}
        ):
            return None
        identity = [
            job.bot_id,
            item.url,
            job.mode,
            item.kind,
            item.title,
            item.performer,
            item.album,
            item.cover_url,
            item.isrc,
            item.duration,
            item.track_number,
            self.policy.music_sources,
            self.policy.video_height,
            self.policy.max_file_bytes,
            self.policy.max_duration_seconds,
            self.policy.music_match_threshold,
            self.policy.music_duration_tolerance,
        ]
        return hashlib.sha256(
            json.dumps(identity, ensure_ascii=False).encode()
        ).hexdigest()
