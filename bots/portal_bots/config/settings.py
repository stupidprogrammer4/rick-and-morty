import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, model_validator


class BotSettings(BaseModel):
    media_token: SecretStr | None = None
    media_webhook_secret: SecretStr | None = Field(default=None, min_length=32)
    media_directory: str = "data/media"
    rick_token: SecretStr
    morty_token: SecretStr
    rick_webhook_secret: SecretStr = Field(min_length=32)
    morty_webhook_secret: SecretStr = Field(min_length=32)
    service_key: SecretStr = Field(min_length=32)
    admin_ids: set[int] = Field(min_length=1)
    api_url: str = "http://api:8000"
    redis_url: str = "redis://redis:6379/0"
    webhook_base_url: str = ""
    port: int = Field(default=8080, ge=1, le=65535)

    @model_validator(mode="after")
    def independent_identities(self):
        if self.media_token is not None:
            if (
                self.media_token in {self.rick_token, self.morty_token}
                or self.media_webhook_secret is None
            ):
                raise ValueError(
                    "Media needs its own token and webhook secret"
                )
            if self.media_webhook_secret in {
                self.rick_webhook_secret,
                self.morty_webhook_secret,
            }:
                raise ValueError("Media webhook secret must be independent")
        if self.rick_token == self.morty_token:
            raise ValueError("Rick and Morty need distinct bot tokens")
        if self.rick_webhook_secret == self.morty_webhook_secret:
            raise ValueError("Each webhook needs an independent secret")
        return self

    @classmethod
    def from_env(cls):
        load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
        return cls(
            media_token=SecretStr(token)
            if (token := os.getenv("MEDIA_DOWNLOADER_TG_BOT"))
            else None,
            media_webhook_secret=SecretStr(secret)
            if (secret := os.getenv("PORTAL_MEDIA_WEBHOOK_SECRET"))
            else None,
            media_directory=os.getenv("PORTAL_MEDIA_DIRECTORY", "data/media"),
            rick_token=SecretStr(
                os.getenv(
                    "PORTAL_RICK_BOT_TOKEN", os.getenv("RICK_TG_BOT", "")
                )
            ),
            morty_token=SecretStr(
                os.getenv(
                    "PORTAL_MORTY_BOT_TOKEN", os.getenv("MORTY_TG_BOT", "")
                )
            ),
            rick_webhook_secret=SecretStr(
                os.getenv("PORTAL_RICK_WEBHOOK_SECRET", "")
            ),
            morty_webhook_secret=SecretStr(
                os.getenv("PORTAL_MORTY_WEBHOOK_SECRET", "")
            ),
            service_key=SecretStr(os.getenv("PORTAL_SERVICE_KEY", "")),
            admin_ids={
                int(value.strip())
                for value in os.getenv("PORTAL_ADMIN_USER_IDS", "").split(",")
                if value.strip()
            },
            api_url=os.getenv("PORTAL_API_URL", "http://api:8000"),
            redis_url=os.getenv("PORTAL_REDIS_URL", "redis://redis:6379/0"),
            webhook_base_url=os.getenv("PORTAL_WEBHOOK_BASE_URL", ""),
            port=int(os.getenv("PORTAL_BOTS_PORT", "8080")),
        )
