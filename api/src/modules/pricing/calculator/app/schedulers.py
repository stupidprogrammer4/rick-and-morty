from taskiq import ScheduledTask, ScheduleSource


class SchedulerService:
    queue_name = "calculator_queue"
    prefix = "calculator:asset:"

    def __init__(self, source: ScheduleSource, task_name: str) -> None:
        self.source = source
        self.task_name = task_name

    async def sync(
        self,
        asset_id: int,
        scheduler_on: bool,
        scheduler_seconds: int,
    ) -> bool:
        """
        Desc: Write the schedule an asset's config asks for, or take away
        the one it had.
        Args:
            asset_id (int): ID of the asset the schedule prices.
            scheduler_on (bool): Whether it is to be priced on a period.
            scheduler_seconds (int): How often, in whole seconds.
        Returns:
            return (bool): Whether the asset is scheduled now.
        """
        schedule_id = f"{self.prefix}{asset_id}"
        await self.source.delete_schedule(schedule_id)
        if scheduler_on:
            await self.source.add_schedule(
                ScheduledTask(
                    task_name=self.task_name,
                    labels={"queue_name": self.queue_name},
                    args=[],
                    kwargs={"asset_id": asset_id},
                    schedule_id=schedule_id,
                    interval=scheduler_seconds,
                )
            )
        return scheduler_on


class BubbleSchedulerService:
    queue_name = "calculator_queue"
    prefix = "calculator:bubble:"

    def __init__(self, source: ScheduleSource, task_name: str) -> None:
        self.source = source
        self.task_name = task_name

    async def sync(
        self,
        bubble_id: int,
        scheduler_on: bool,
        scheduler_seconds: int,
    ) -> bool:
        """
        Desc: Write the schedule a bubble's config asks for, or take away
        the one it had.
        Args:
            bubble_id (int): ID of the bubble the schedule settles.
            scheduler_on (bool): Whether it is to be settled on a period.
            scheduler_seconds (int): How often, in whole seconds.
        Returns:
            return (bool): Whether the bubble is scheduled now.
        """
        schedule_id = f"{self.prefix}{bubble_id}"
        await self.source.delete_schedule(schedule_id)
        if scheduler_on:
            await self.source.add_schedule(
                ScheduledTask(
                    task_name=self.task_name,
                    labels={"queue_name": self.queue_name},
                    args=[],
                    kwargs={"bubble_id": bubble_id},
                    schedule_id=schedule_id,
                    interval=scheduler_seconds,
                )
            )
        return scheduler_on
