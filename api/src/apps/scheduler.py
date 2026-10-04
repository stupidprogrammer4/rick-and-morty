import os

from dotenv import load_dotenv
from papilio.core.config import get_settings
from papilio_tasks.apps.schedulers.redis import create_app

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.config.task_compatibility import register_legacy_tasks

load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
settings = get_settings(PortalAppSettings)
app = create_app(
    settings.tasks,
    providers=task_providers(settings),
    modules=settings.app.modules,
)
register_legacy_tasks(app.broker)
broker, scheduler = app.broker, app.scheduler
