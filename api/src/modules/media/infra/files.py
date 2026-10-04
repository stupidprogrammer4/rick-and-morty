import asyncio
import shutil
from collections.abc import Sequence
from pathlib import Path

from src.config.settings import PortalAppSettings
from src.modules.media.domain.dtos import MediaDiskUsage, MediaDownloadInput


class MediaFiles:
    def __init__(self, settings: PortalAppSettings):
        self.root = Path(settings.media.directory)

    def directory(self, id: int) -> Path:
        if id <= 0:
            raise ValueError("Invalid job ID")
        return self.root / str(id)

    def plan_directory(self, id: int) -> Path:
        return self.directory(id) / "plan"

    def item_directory(self, job_id: int, item_id: int) -> Path:
        if item_id <= 0:
            raise ValueError("Invalid item ID")
        return self.directory(job_id) / str(item_id)

    def _usage(self) -> MediaDiskUsage:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        used = sum(
            path.stat().st_size
            for path in self.root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        return MediaDiskUsage(
            used_bytes=used, free_bytes=shutil.disk_usage(self.root).free
        )

    async def usage(self) -> MediaDiskUsage:
        result = await asyncio.to_thread(self._usage)
        return result

    def _prepare(self, id: int) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = self.plan_directory(id)
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(mode=0o700, parents=True)

    async def prepare(self, id: int) -> None:
        await asyncio.to_thread(self._prepare, id)

    async def remove(self, id: int) -> None:
        await asyncio.to_thread(shutil.rmtree, self.directory(id), True)

    def _prepare_item(self, job_id: int, item_id: int) -> None:
        directory = self.item_directory(job_id, item_id)
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(mode=0o700, parents=True)

    async def prepare_item(self, job_id: int, item_id: int) -> None:
        await asyncio.to_thread(self._prepare_item, job_id, item_id)

    async def prepare_many(self, inputs: Sequence[MediaDownloadInput]) -> None:
        await asyncio.gather(
            *(
                asyncio.to_thread(
                    self._prepare_item, data.job.id, data.item.id
                )
                for data in inputs
            )
        )

    async def remove_many(self, inputs: Sequence[MediaDownloadInput]) -> None:
        await asyncio.gather(
            *(
                asyncio.to_thread(
                    self._remove_child,
                    self.item_directory(data.job.id, data.item.id),
                )
                for data in inputs
            )
        )

    def _remove_child(self, path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)
        try:
            path.parent.rmdir()
        except (FileNotFoundError, OSError):
            pass

    async def remove_plan(self, id: int) -> None:
        await asyncio.to_thread(self._remove_child, self.plan_directory(id))

    async def remove_item(self, job_id: int, item_id: int) -> None:
        await asyncio.to_thread(
            self._remove_child, self.item_directory(job_id, item_id)
        )

    def _clean(self, active: set[int], cutoff: float) -> None:
        if not self.root.exists():
            return
        for path in self.root.iterdir():
            if (
                path.is_symlink()
                or not path.is_dir()
                or not path.name.isdecimal()
                or int(path.name) in active
            ):
                continue
            newest = max(
                [
                    path.stat().st_mtime,
                    *(
                        entry.stat().st_mtime
                        for entry in path.rglob("*")
                        if not entry.is_symlink()
                    ),
                ]
            )
            if newest <= cutoff:
                shutil.rmtree(path)

    async def clean(self, active: set[int], cutoff: float) -> None:
        await asyncio.to_thread(self._clean, active, cutoff)
