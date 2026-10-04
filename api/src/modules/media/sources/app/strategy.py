from urllib.parse import urlsplit

from portal_contracts.media import MediaPolicy
from src.modules.media.sources.domain.dtos import DownloadStage, SourceJob


class MediaSourceStrategy:
    def __init__(self, policy: MediaPolicy):
        self.policy = policy

    def stages(self, job: SourceJob) -> list[DownloadStage]:
        parsed = urlsplit(job.url)
        if "direct" in self.policy.providers and parsed.path.lower().endswith(
            (".mp4", ".mp3", ".m4a", ".jpg", ".png", ".webm", ".ogg", ".pdf")
        ):
            return ["direct"]
        route = job.provider
        if job.provider == "instagram" and parsed.path.startswith(
            ("/reel/", "/reels/")
        ):
            route = "instagram.reel"
        return [
            stage
            for stage in self.policy.source_routes.get(route, [])
            if stage != "browser" or self.policy.browser_enabled
        ]
