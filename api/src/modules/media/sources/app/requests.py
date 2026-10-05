from collections.abc import Sequence

from portal_contracts.media import MediaPolicy
from src.config.settings import PortalAppSettings
from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadProcessRequest,
    DownloadStage,
    SourceJob,
)
from src.modules.media.storage.infra.files import MediaFiles


class MediaExtractionRequests:
    def __init__(
        self,
        files: MediaFiles,
        policy: MediaPolicy,
        settings: PortalAppSettings,
    ):
        self.files = files
        self.policy = policy
        self.settings = settings

    def plan(
        self, job: SourceJob, stages: Sequence[DownloadStage]
    ) -> DownloadProcessRequest:
        return DownloadProcessRequest(
            operation="plan",
            url=job.url,
            provider=job.provider,
            mode=job.mode,
            policy=self.policy,
            directory=str(self.files.plan_directory(job.id)),
            cookie_file=self.settings.media.cookie_files.get(job.provider),
            stages=list(stages),
        )

    def file(
        self, job: SourceJob, item_id: int, item: DownloadItem
    ) -> DownloadProcessRequest:
        return DownloadProcessRequest(
            operation="download",
            url=job.url,
            provider=job.provider,
            mode=job.mode,
            policy=self.policy,
            directory=str(self.files.item_directory(job.id, item_id)),
            cookie_file=self.settings.media.cookie_files.get(job.provider),
            item=item,
        )
