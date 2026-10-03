import os

from dotenv import load_dotenv
from papilio.api.application import create_app
from papilio.core.config import get_settings

from src.config.providers import infrastructure_providers
from src.config.settings import PortalAppSettings

load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
settings = get_settings(PortalAppSettings)
app = create_app(
    settings,
    providers=infrastructure_providers(settings),
    middleware=[],
)
