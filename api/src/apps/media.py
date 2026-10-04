from dataclasses import replace

from papilio.core.config import get_settings
from papilio_tasks.apps.schedulers.redis import create_app

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.media_tasks.providers import MediaTaskProvider

settings = get_settings(PortalAppSettings)
media_settings = replace(
    settings.tasks,
    queue_name=settings.tasks.queue_name + ":media",
    schedule_prefix=settings.tasks.schedule_prefix + ":media",
    consumer_group=settings.tasks.consumer_group + ":media",
    result_prefix=settings.tasks.result_prefix + ":media",
)
app = create_app(
    media_settings,
    providers=[*task_providers(settings), MediaTaskProvider()],
    modules=["src.media_tasks"],
)
broker, scheduler = app.broker, app.scheduler
