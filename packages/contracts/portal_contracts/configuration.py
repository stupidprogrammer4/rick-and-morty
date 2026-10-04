from datetime import time
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from portal_contracts.charts import AssetChartPolicy
from portal_contracts.presentation import PortalPresentation


class SettingKey(StrEnum):
    PORTAL = "portal.policy"
    AI = "ai.model"
    MARKET = "market.policy"
    PRESENTATION = "presentation"
    VOICE = "voice"
    POST = "post.style"
    QUOTE = "market.quote"
    AUTOMATION = "automation.policy"
    ENGINE = "market.engine"
    MEDIA = "media.policy"


class SettingScope(StrEnum):
    GLOBAL = "global"
    RICK = "rick"
    MORTY = "morty"
    NEWS = "news"
    TECH = "tech"
    MARKET = "market"
    MUSIC = "music"
    NOTICE = "notice"
    GOLD = "gold"
    USD = "usd"
    SILVER = "silver"


class PortalPolicy(BaseModel):
    channel_id: int | None
    timezone: str
    daily_post_cap: int = Field(ge=1, le=100)
    quiet_start: time
    quiet_end: time
    mission_timeout: int = Field(ge=10, le=600)
    mission_concurrency: int = Field(ge=1, le=10)
    publication_timeout: int = Field(ge=60, le=86400)
    task_history_seconds: int = Field(default=3600, ge=60, le=86400)

    @model_validator(mode="after")
    def timezone_exists(self) -> Self:
        ZoneInfo(self.timezone)
        if self.channel_id is not None and self.channel_id >= 0:
            raise ValueError("Channel ID must be a negative Telegram ID")
        return self


class EffectivePortalPolicy(PortalPolicy):
    dry_run: bool


class AIModelPolicy(BaseModel):
    mode: Literal["disabled", "fake", "openrouter"]
    model: str = Field(max_length=200)
    max_requests: int = Field(ge=1, le=10)
    max_tools: int = Field(ge=1, le=20)
    max_reactions: int = Field(ge=0, le=5)
    max_input_tokens: int = Field(ge=1000, le=100000)
    max_output_tokens: int = Field(ge=100, le=4000)
    daily_budget_usd: Decimal = Field(gt=0, allow_inf_nan=False)
    maximum_request_usd: Decimal = Field(
        default=Decimal("0"), ge=0, allow_inf_nan=False
    )
    allow_data_collection: bool = False
    input_usd_per_million: Decimal | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    output_usd_per_million: Decimal | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def live_model_is_priced(self) -> Self:
        if self.mode == "openrouter" and (
            not self.model.strip()
            or self.input_usd_per_million is None
            or self.output_usd_per_million is None
        ):
            raise ValueError("Select a model and its input/output prices")
        return self


class MarketInstrument(BaseModel):
    symbol: Literal["gold", "usd", "silver", "usdt"]
    label: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    purity: str | None = None
    market: str | None = None

    @model_validator(mode="after")
    def unit_is_explicit(self) -> Self:
        if self.symbol in {"gold", "silver"} and not self.purity:
            raise ValueError("Metal purity must be explicit")
        if self.symbol in {"usd", "usdt"} and not self.market:
            raise ValueError("Currency market must be explicit")
        return self


class MarketPolicy(BaseModel):
    charts: AssetChartPolicy = Field(default_factory=AssetChartPolicy)
    backend: Literal["talamala", "auryx"] = "talamala"
    report_mode: Literal["aggregate", "sources"] = "aggregate"
    instruments: dict[str, MarketInstrument] = Field(default_factory=dict)
    enabled: bool
    allowed_hosts: set[str] = Field(min_length=1)
    max_age_seconds: int = Field(gt=0, le=86400)
    future_skew_seconds: int = Field(ge=0, le=600)

    @model_validator(mode="after")
    def source_report_has_instruments(self) -> Self:
        if self.report_mode == "sources" and not self.instruments:
            raise ValueError("Source reports require configured instruments")
        return self


class MarketEnginePolicy(BaseModel):
    source_timeout: int = Field(ge=1, le=60)
    asset_interval: int = Field(ge=20, le=300)
    usd_interval: int = Field(ge=20, le=300)
    aggregation: Literal[
        "median", "mean", "min", "max", "first_quartile", "third_quartile"
    ]
    asset_scheduler_on: bool
    usd_scheduler_on: bool
    bubble_scheduler_on: bool
    outlier_rate: float = Field(gt=0, le=1)
    min_outlier_sample: int = Field(ge=3, le=100)
    max_quote_age_seconds: int = Field(ge=30, le=86400)


class ContentSchedule(BaseModel):
    enabled: bool
    interval_seconds: int = Field(ge=60, le=604800)
    starts_at: AwareDatetime
    topic: str = Field(min_length=1, max_length=64)
    lookback_seconds: int = Field(ge=60, le=604800)
    prompt: str = Field(min_length=1, max_length=4000)


class AutomationPolicy(BaseModel):
    owner_id: int | None = Field(default=None, gt=0)
    news: ContentSchedule
    prices: ContentSchedule

    @model_validator(mode="after")
    def enabled_schedules_have_owner(self) -> Self:
        if (
            self.news.enabled or self.prices.enabled
        ) and self.owner_id is None:
            raise ValueError("Enabled schedules require an owner")
        return self


class PortalConfiguration(BaseModel):
    portal: EffectivePortalPolicy
    ai: AIModelPolicy
    market: MarketPolicy
    automation: AutomationPolicy


class SettingDefinitionCreate(BaseModel):
    key: SettingKey
    title: str = Field(min_length=1, max_length=100)


class SettingDefinitionOut(SettingDefinitionCreate):
    id: int
    kind: Literal["json"]


class SettingValueWrite(BaseModel):
    value: str = Field(min_length=2, max_length=50000)
    revision: int = Field(ge=0)


class SettingValueOut(BaseModel):
    definition_id: int
    key: SettingKey
    scope: SettingScope
    value_id: int | None
    value: str | None
    revision: int


class BotConfiguration(BaseModel):
    channel_id: int | None
    presentation: PortalPresentation


class SettingSchemaOut(BaseModel):
    schema_definition: dict


class EntityWritten(BaseModel):
    id: int
