from collections.abc import Sequence
from typing import Protocol

from portal_contracts.configuration import (
    SettingDefinitionCreate,
    SettingDefinitionOut,
    SettingKey,
    SettingScope,
    SettingValueOut,
    SettingValueWrite,
)
from src.modules.configuration.domain.dtos import (
    ConfigurationSeed,
    ConfigurationSnapshot,
    NewsSourceCatalog,
    NewsSourceConfigWrite,
    NewsSourceCreate,
    NewsSourceOptions,
    NewsSourcePage,
    NewsSourceUpdate,
)
from src.modules.configuration.domain.models import (
    NewsSourceConfigModel,
    NewsSourceModel,
    SettingDefinitionModel,
    SettingValueModel,
)


class ISettingDefinitionService(Protocol):
    async def get(self, key: SettingKey) -> SettingDefinitionModel: ...

    async def all(self) -> list[SettingDefinitionOut]: ...

    async def create(
        self, data: SettingDefinitionCreate
    ) -> SettingDefinitionOut: ...

    async def seed_many(
        self, rows: Sequence[SettingDefinitionModel]
    ) -> None: ...


class ISettingValueService(Protocol):
    async def get(
        self, key: SettingKey, scope: SettingScope
    ) -> SettingValueOut: ...

    async def write(
        self, key: SettingKey, scope: SettingScope, data: SettingValueWrite
    ) -> SettingValueOut: ...

    async def seed_many(self, rows: Sequence[SettingValueModel]) -> None: ...


class INewsSourceService(Protocol):
    async def get(self, id: int) -> NewsSourceModel: ...

    async def all(self) -> Sequence[NewsSourceModel]: ...

    async def create(self, data: NewsSourceCreate) -> NewsSourceModel: ...

    async def update(
        self, id: int, data: NewsSourceUpdate
    ) -> NewsSourceModel: ...

    async def seed_many(self, rows: Sequence[NewsSourceModel]) -> None: ...


class INewsSourceConfigService(Protocol):
    async def create(
        self, source_id: int, options: NewsSourceOptions
    ) -> NewsSourceConfigModel: ...

    async def update(
        self, id: int, data: NewsSourceConfigWrite
    ) -> NewsSourceConfigModel: ...

    async def seed_many(
        self, rows: Sequence[NewsSourceConfigModel]
    ) -> None: ...


class IConfigurationQueries(Protocol):
    async def editable(self) -> list[SettingValueOut]: ...

    async def sources(self, page: int, per_page: int) -> NewsSourcePage: ...

    async def news_catalog(self) -> NewsSourceCatalog: ...

    async def snapshot(self) -> ConfigurationSnapshot: ...


class IConfigurationCommands(Protocol):
    async def create_source(self, data: NewsSourceCreate) -> int: ...

    async def seed(self, data: ConfigurationSeed) -> None: ...
