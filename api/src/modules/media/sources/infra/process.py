import asyncio
import json
import os
import signal
import sys
from pathlib import Path

from src.modules.media.sources.domain.dtos import DownloadProcessRequest


class MediaExtractorProcess:
    async def execute(self, request: DownloadProcessRequest) -> str:
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
        environment["XDG_CACHE_HOME"] = str(Path(request.directory) / "cache")
        environment["XDG_CONFIG_HOME"] = str(
            Path(request.directory) / "config"
        )
        environment["TMPDIR"] = request.directory
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "src.modules.media.sources.infra.downloaders.process",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
        )
        try:
            async with asyncio.timeout(request.policy.item_timeout_seconds):
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
