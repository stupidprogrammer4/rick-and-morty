import asyncio
from collections.abc import Sequence

from src.modules.media.sources.app.requests import MediaExtractionRequests
from src.modules.media.sources.domain.dtos import (
    DownloadPlan,
    DownloadStage,
    SourceJob,
)
from src.modules.media.sources.infra.extraction import PublicMediaExtraction
from src.modules.media.sources.infra.process import MediaExtractorProcess


class MediaSourcePlanner:
    def __init__(
        self,
        requests: MediaExtractionRequests,
        public: PublicMediaExtraction,
        process: MediaExtractorProcess,
    ):
        self.requests = requests
        self.public = public
        self.process = process

    async def plan(
        self, job: SourceJob, stages: Sequence[DownloadStage]
    ) -> DownloadPlan:
        request = self.requests.plan(job, stages)
        if not request.stages:
            raise ValueError("No extractors are enabled for this source")
        async with asyncio.timeout(request.policy.item_timeout_seconds):
            if request.stages[0] in {"direct", "instagram", "pinterest"}:
                try:
                    result = await self.public.plan(request)
                    return result
                except Exception as exc:
                    if len(request.stages) == 1:
                        raise
                    request = request.model_copy(
                        update={"stages": request.stages[1:]}
                    )
                    public_error = str(exc)[:220]
                try:
                    raw = await self.process.execute(request)
                except Exception as exc:
                    raise ValueError(
                        public_error + "; " + str(exc)[:220]
                    ) from exc
            else:
                raw = await self.process.execute(request)
            return DownloadPlan.model_validate_json(raw)
