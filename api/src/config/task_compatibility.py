from taskiq import AsyncBroker

LEGACY_TASK_NAMES = {
    ("src.modules.missions.tasks.schedulers.execute.ExecuteMission"): (
        "src.modules.automation.missions.tasks.schedulers.execute."
        "ExecuteMission"
    ),
    ("src.modules.missions.tasks.schedulers.execute.RecoverMissions"): (
        "src.modules.automation.missions.tasks.schedulers.execute."
        "RecoverMissions"
    ),
    ("src.modules.missions.tasks.schedulers.execute.ScheduleContent"): (
        "src.modules.automation.missions.tasks.schedulers.execute."
        "ScheduleContent"
    ),
    ("src.modules.ops.tasks.schedulers.maintenance.PruneTaskHistory"): (
        "src.modules.ops.queues.tasks.schedulers.maintenance.PruneTaskHistory"
    ),
    ("src.modules.publishing.tasks.schedulers.dispatch.DispatchPublication"): (
        "src.modules.content.publications.tasks.schedulers.dispatch."
        "DispatchPublication"
    ),
    ("src.modules.publishing.tasks.schedulers.dispatch.DispatchReply"): (
        "src.modules.content.replies.tasks.schedulers.dispatch.DispatchReply"
    ),
    ("src.modules.publishing.tasks.schedulers.dispatch.RecoverPublications"): (
        "src.modules.content.publications.tasks.schedulers.dispatch."
        "RecoverPublications"
    ),
    ("src.modules.publishing.tasks.schedulers.dispatch.RecoverReplies"): (
        "src.modules.content.replies.tasks.schedulers.dispatch.RecoverReplies"
    ),
    ("src.modules.publishing.tasks.schedulers.dispatch.DispatchChart"): (
        "src.modules.content.publications.tasks.schedulers.dispatch."
        "DispatchChart"
    ),
    ("src.modules.publishing.tasks.schedulers.dispatch.RecoverCharts"): (
        "src.modules.content.publications.tasks.schedulers.dispatch."
        "RecoverCharts"
    ),
}


def register_legacy_tasks(broker: AsyncBroker) -> None:
    for old_name, current_name in LEGACY_TASK_NAMES.items():
        task = broker.find_task(current_name)
        if task is None:
            raise RuntimeError(f"Missing moved task: {current_name}")
        labels = {
            key: value
            for key, value in task.labels.items()
            if key != "schedule"
        }
        broker.register_task(task.original_func, task_name=old_name, **labels)
