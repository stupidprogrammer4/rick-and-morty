import os
from typing import Any, Self

from papilio.core.config import Settings
from papilio_tasks.apps.taskiq import RedisSettings
from pydantic import BaseModel, Field, SecretStr, model_validator


class SecuritySettings(BaseModel):
    service_key: SecretStr = Field(min_length=32)
    admin_ids: list[int] = Field(min_length=1)


class TransportSettings(BaseModel):
    dry_run: bool = True
    gateway_url: str = "http://bots:8080"


class ModelCredentials(BaseModel):
    api_key: SecretStr = SecretStr("")


class MarketCredentials(BaseModel):
    token: SecretStr = SecretStr("")


class PortalAppSettings(Settings):
    security: SecuritySettings
    portal: TransportSettings = Field(default_factory=TransportSettings)
    ai: ModelCredentials = Field(default_factory=ModelCredentials)
    market: MarketCredentials = Field(default_factory=MarketCredentials)
    tasks: RedisSettings

    @model_validator(mode="before")
    @classmethod
    def environment(cls, raw: Any) -> Any:
        data = dict(raw)
        security = dict(data.get("security", {}))
        if key := os.getenv("PORTAL_SERVICE_KEY"):
            security["service_key"] = key
        if ids := os.getenv("PORTAL_ADMIN_USER_IDS"):
            security["admin_ids"] = [int(x.strip()) for x in ids.split(",")]
        data["security"] = security
        database = dict(data.get("db", {}))
        if dsn := os.getenv("PORTAL_DATABASE_URL"):
            database["dsn"] = dsn
        data["db"] = database
        tasks = dict(data.get("tasks", {}))
        if url := os.getenv("PORTAL_REDIS_URL"):
            tasks["url"] = url
        data["tasks"] = tasks
        portal = dict(data.get("portal", {}))
        if dry := os.getenv("PORTAL_DRY_RUN"):
            if dry.lower() not in {"true", "false"}:
                raise ValueError("PORTAL_DRY_RUN must be true or false")
            portal["dry_run"] = dry.lower() == "true"
        data["portal"] = portal
        ai = dict(data.get("ai", {}))
        if key := os.getenv("OPENROUTER_API_KEY"):
            ai["api_key"] = key
        data["ai"] = ai
        market = dict(data.get("market", {}))
        if token := os.getenv("TALAMALA_API_TOKEN"):
            market["token"] = token
        data["market"] = market
        return data

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        if self.db is None or not self.db.dsn.startswith("mysql+aiomysql://"):
            raise ValueError("Configure MySQL with the aiomysql driver")
        return self
