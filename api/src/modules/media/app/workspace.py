from collections.abc import Sequence

from portal_contracts.media import MediaPolicy
from src.modules.media.domain.dtos import MediaDownloadInput
from src.modules.media.infra.files import MediaFiles


class MediaWorkspace:
    def __init__(self, files: MediaFiles, policy: MediaPolicy):
        self.files = files
        self.policy = policy

    async def prepare(self, id: int) -> None:
        usage = await self.files.usage()
        reservation = self.policy.max_file_bytes * 3
        if (
            usage.used_bytes + reservation > self.policy.disk_budget_bytes
            or usage.free_bytes < self.policy.disk_reserve_bytes + reservation
        ):
            raise ValueError("فضای امن برای دانلود کافی نیست؛ بعداً امتحان کن.")
        await self.files.prepare(id)

    async def prepare_item(self, job_id: int, item_id: int) -> None:
        usage = await self.files.usage()
        reservation = self.policy.max_file_bytes * 3
        if (
            usage.used_bytes + reservation > self.policy.disk_budget_bytes
            or usage.free_bytes < self.policy.disk_reserve_bytes + reservation
        ):
            raise ValueError("فضای امن برای دانلود کافی نیست؛ بعداً امتحان کن.")
        await self.files.prepare_item(job_id, item_id)

    async def prepare_many(self, inputs: Sequence[MediaDownloadInput]) -> None:
        usage = await self.files.usage()
        reservation = self.policy.max_file_bytes * 3 * len(inputs)
        if (
            usage.used_bytes + reservation > self.policy.disk_budget_bytes
            or usage.free_bytes < self.policy.disk_reserve_bytes + reservation
        ):
            raise ValueError("فضای امن برای دانلود کافی نیست؛ بعداً امتحان کن.")
        await self.files.prepare_many(inputs)
