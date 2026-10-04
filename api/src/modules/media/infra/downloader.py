import asyncio
import json
import os
import signal
import sys
from typing import Literal

from portal_contracts.media import MediaPolicy
from src.config.settings import PortalAppSettings
from src.modules.media.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
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
    ) -> str:
        request = DownloadProcessRequest(
            operation=operation,
            url=job.url,
            provider=job.provider,
            mode=job.mode,
            policy=self.policy,
            directory=str(self.files.directory(job.id)),
            item=item,
            cookie_file=self.settings.media.cookie_files.get(job.provider),
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
        environment["XDG_CACHE_HOME"] = str(
            self.files.directory(job.id) / "cache"
        )
        environment["XDG_CONFIG_HOME"] = str(
            self.files.directory(job.id) / "config"
        )
        environment["TMPDIR"] = str(self.files.directory(job.id))
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

    async def plan(self, job: MediaJobModel) -> DownloadPlan:
        raw = await self.run(job, "plan")
        return DownloadPlan.model_validate_json(raw)

    async def download(
        self, job: MediaJobModel, item: DownloadItem
    ) -> DownloadedFile:
        raw = await self.run(job, "download", item)
        return DownloadedFile.model_validate_json(raw)
