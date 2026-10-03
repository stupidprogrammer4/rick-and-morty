import asyncio
from collections import Counter

from papilio.infra.db.tools.decorators import transactional
from papilio_tasks.infra.taskiq.sources.backends.redis import RedisSource
from taskiq import ScheduledTask

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.infra.schedules import ScheduleReader


class ReconcileSchedules:
    def __init__(
        self,
        reader: ScheduleReader,
        source: RedisSource,
        asset_task: str,
        bubble_task: str,
        usd_task: str,
    ) -> None:
        self.reader = reader
        self.source = source
        self.task_names = {"asset": asset_task, "bubble": bubble_task}
        self.usd_task = usd_task

    @transactional
    async def execute(self) -> int:
        """Repair committed schedules without resetting matching timers."""
        if not await self.reader.try_lock():
            return 0
        configs = await self.reader.get_all()
        expected = {
            f"calculator:{config.kind}:{config.id}": ScheduledTask(
                task_name=self.usd_task
                if config.kind == "asset" and config.code == AssetCode.USD
                else self.task_names[config.kind],
                labels={},
                args=[],
                kwargs={}
                if config.kind == "asset" and config.code == AssetCode.USD
                else {f"{config.kind}_id": config.id},
                schedule_id=f"calculator:{config.kind}:{config.id}",
                interval=config.scheduler_seconds,
            )
            for config in configs
            if config.scheduler_on
        }
        stored = await self.source.list_schedules()
        current = {
            item.schedule_id: item
            for item in stored
            if item.schedule_id.startswith(
                ("calculator:asset:", "calculator:bubble:")
            )
        }
        # Payload presence does not prove insertion into the timing feed.
        feed = await self.source.get_schedules()
        occurrences = Counter(item.schedule_id for item in feed)
        changed = {
            key
            for key in current.keys() | expected.keys()
            if current.get(key) != expected.get(key)
            or (key in expected and occurrences[key] != 1)
        }
        results = await asyncio.gather(
            *(self.repair(key, expected.get(key)) for key in changed),
            return_exceptions=True,
        )
        failures = [
            result for result in results if isinstance(result, BaseException)
        ]
        if failures:
            raise BaseExceptionGroup(
                "Calculator schedule repair failed", failures
            )
        return len(changed)

    async def repair(self, id: str, schedule: ScheduledTask | None) -> None:
        """Replace one owned schedule; a failed write is retried next pass."""
        await self.source.delete_schedule(id)
        if schedule is not None:
            await self.source.add_schedule(schedule)
