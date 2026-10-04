from urllib.parse import urlsplit

from portal_contracts.media import MediaPolicy
from src.modules.media.domain.dtos import DownloadStage
from src.modules.media.domain.models import MediaJobModel


class MediaSourceStrategy:
    def __init__(self, policy: MediaPolicy):
        self.policy = policy

    def stages(self, job: MediaJobModel) -> list[DownloadStage]:
        if job.provider == "spotify":
            return ["spotify"]
        if "direct" in self.policy.providers and urlsplit(
            job.url
        ).path.lower().endswith(
            (".mp4", ".mp3", ".m4a", ".jpg", ".png", ".webm", ".ogg", ".pdf")
        ):
            return ["direct"]
        order: list[DownloadStage] = (
            ["gallery", "video"]
            if job.provider == "instagram"
            else ["video", "gallery"]
        )
        stages: list[DownloadStage] = [
            stage
            for stage in order
            if stage in self.policy.providers
            or job.provider in self.policy.providers
        ]
        if self.policy.browser_enabled and "browser" in self.policy.providers:
            stages.append("browser")
        return stages
