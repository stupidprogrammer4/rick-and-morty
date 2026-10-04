from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.content.publications.interfaces import (
    IPublicationChartCommands,
    IPublicationChartRecovery,
    IPublicationCommands,
    IPublicationRecovery,
)


class DispatchPublication(RedisScheduler):
    def __init__(self, command: IPublicationCommands):
        self.command = command

    async def run(self, publication_id: int) -> None:
        await self.command.dispatch(publication_id)


class RecoverPublications(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, recovery: IPublicationRecovery):
        self.recovery = recovery

    async def run(self) -> None:
        await self.recovery.enqueue_pending()


class DispatchChart(RedisScheduler):
    def __init__(self, commands: IPublicationChartCommands):
        self.commands = commands

    async def run(self, chart_id: int) -> None:
        await self.commands.dispatch(chart_id)


class RecoverCharts(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, recovery: IPublicationChartRecovery):
        self.recovery = recovery

    async def run(self) -> None:
        await self.recovery.enqueue_pending()
