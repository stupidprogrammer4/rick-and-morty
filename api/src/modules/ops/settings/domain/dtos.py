from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from portal_contracts.configuration import (
    MarketEnginePolicy,
    PortalConfiguration,
    SettingDefinitionCreate,
    SettingScope,
)
from portal_contracts.presentation import PortalPresentation
from src.modules.content.news.domain.dtos import NewsSource
from src.modules.pricing.reports.domain.dtos import PriceMapping


class NewsSourceOptions(BaseModel):
    allowed_hosts: set[str] = Field(min_length=1)
    topics: set[str] = Field(min_length=1)
    external_articles: bool
    default_topics: list[str]
    search_page_size: int = Field(ge=1, le=50)


class NewsSourceCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=100)
    kind: Literal["rss", "hackernews"]
    feed_url: HttpUrl
    enabled: bool
    options: NewsSourceOptions


class NewsSourceUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    feed_url: HttpUrl
    enabled: bool
    revision: int = Field(ge=1)


class NewsSourceConfigWrite(BaseModel):
    options: NewsSourceOptions
    revision: int = Field(ge=1)


class NewsSourceRead(NewsSourceCreate):
    id: int
    revision: int
    config_revision: int


class NewsSourcePage(BaseModel):
    items: list[NewsSourceRead]
    total: int
    page: int
    per_page: int


class NewsSourceCatalog(BaseModel):
    sources: list[NewsSource]


class ConfigurationSnapshot(BaseModel):
    configuration: PortalConfiguration
    presentation: PortalPresentation
    prices: PriceMapping
    engine: MarketEnginePolicy


class SeedValue(BaseModel):
    key: str
    scope: SettingScope
    value: str


class ConfigurationSeed(BaseModel):
    definitions: list[SettingDefinitionCreate]
    values: list[SeedValue]
    sources: list[NewsSourceCreate]
