import asyncio
import json
import os
import signal
import sys
from collections.abc import Sequence
from typing import Literal

from portal_contracts.media import MediaPolicy
from src.config.settings import PortalAppSettings
from src.modules.media.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
    DownloadStage,
    MediaDownloadInput,
    MediaDownloadOutcome,
    MediaDownloadSink,
)
from src.modules.media.domain.models import MediaJobModel
from src.modules.media.infra.files import MediaFiles


class MediaDownloader:
    def __init__(
        self,
        files: MediaFiles,
        policy: MediaPolicy,
        settings: PortalAppSettings,
    ):
        self.files = files
        self.policy = policy
        self.settings = settings

    async def run(
        self,
        job: MediaJobModel,
        operation: Literal["plan", "download"],
        item: DownloadItem | None = None,
        item_id: int | None = None,
        stages: Sequence[DownloadStage] = (),
    ) -> str:
        directory = (
            self.files.item_directory(job.id, item_id)
            if item_id is not None
            else self.files.plan_directory(job.id)
        )
        request = DownloadProcessRequest(
            operation=operation,
            url=job.url,
            provider=job.provider,
            mode=job.mode,
            policy=self.policy,
            directory=str(directory),
            item=item,
            cookie_file=self.settings.media.cookie_files.get(job.provider),
            stages=list(stages),
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "PYTHONPATH",
                "LANG",
                "LC_ALL",
                "PLAYWRIGHT_BROWSERS_PATH",
                "PORTAL_BROWSER_EXECUTABLE",
                "SPOTIPY_CLIENT_ID",
                "SPOTIPY_CLIENT_SECRET",
            }
        }
        environment["XDG_CACHE_HOME"] = str(directory / "cache")
        environment["XDG_CONFIG_HOME"] = str(directory / "config")
        environment["TMPDIR"] = str(directory)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "src.modules.media.infra.downloaders.process",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
        )
        try:
            async with asyncio.timeout(self.policy.item_timeout_seconds):
                stdout, _ = await process.communicate(
                    request.model_dump_json().encode()
                )
        finally:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
        if len(stdout) > 4_000_000:
            raise ValueError("Extractor result exceeded the metadata budget")
        if process.returncode:
            try:
                detail = json.loads(stdout)
                message = detail.get("message", "Media extraction failed")
            except ValueError:
                message = "Media extraction failed"
            raise ValueError(message)
        return stdout.decode()

    async def plan(
        self, job: MediaJobModel, stages: Sequence[DownloadStage]
    ) -> DownloadPlan:
        raw = await self.run(job, "plan", stages=stages)
        return DownloadPlan.model_validate_json(raw)

    async def download(
        self, job: MediaJobModel, item_id: int, item: DownloadItem
    ) -> DownloadedFile:
        raw = await self.run(job, "download", item, item_id=item_id)
        return DownloadedFile.model_validate_json(raw)

    async def download_many(
        self,
        inputs: Sequence[MediaDownloadInput],
        completed: MediaDownloadSink,
    ) -> list[MediaDownloadOutcome]:
        responses = await asyncio.gather(
            *(self.receive(data, completed) for data in inputs),
            return_exceptions=True,
        )
        if any(isinstance(response, BaseException) for response in responses):
            raise ValueError("Unable to publish one or more download results")
        return [
            response
            for response in responses
            if isinstance(response, MediaDownloadOutcome)
        ]

    async def receive(
        self, data: MediaDownloadInput, completed: MediaDownloadSink
    ) -> MediaDownloadOutcome:
        try:
            raw = await self.run(
                data.job,
                "download",
                DownloadItem.model_validate_json(data.item.payload),
                item_id=data.item.id,
            )
        except Exception as exc:
            outcome = self.outcome(data, exc)
        else:
            outcome = self.outcome(data, raw)
        await completed(outcome)
        return outcome

    def outcome(
        self, data: MediaDownloadInput, response: str | BaseException
    ) -> MediaDownloadOutcome:
        if isinstance(response, BaseException):
            return MediaDownloadOutcome(
                item_id=data.item.id,
                job_id=data.job.id,
                lease_until=data.item.lease_until,
                error=type(response).__name__ + ": " + str(response)[:350],
            )
        try:
            downloaded = DownloadedFile.model_validate_json(response)
        except ValueError as exc:
            return MediaDownloadOutcome(
                item_id=data.item.id,
                job_id=data.job.id,
                lease_until=data.item.lease_until,
                error=type(exc).__name__ + ": " + str(exc)[:350],
            )
        return MediaDownloadOutcome(
            item_id=data.item.id,
            job_id=data.job.id,
            lease_until=data.item.lease_until,
            downloaded=downloaded,
        )
