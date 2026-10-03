from collections.abc import Awaitable
from typing import Mapping, Protocol, Sequence

from papilio.errors.exceptions import ValidationException
from papilio.schemas.results import BatchResultType, PagedType

from src.modules.pricing.sources.domain.dtos import (
    SourceConfigUpdate,
    SourceCreate,
    SourceSearch,
    SourceUpdate,
)
from src.modules.pricing.sources.domain.enums import SourceSwitch
from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.sources.domain.models import (
    SourceConfigModel,
    SourceModel,
    SourceOnlyMetaModel,
    SourcesMetaModel,
    SourceWithConfigModel,
)
from src.modules.pricing.sources.domain.results import (
    MultiSourcePricesResult,
    SourceErrorRemoval,
    SourcePricesResult,
)
from src.modules.pricing.symbols.domain.models import SymbolModel


class ISourceConfigService(Protocol):
    def create_default(
        self, source_id: int
    ) -> Awaitable[SourceConfigModel]: ...

    def create_defaults(
        self, source_ids: Sequence[int]
    ) -> Awaitable[Sequence[SourceConfigModel]]: ...

    def update(
        self,
        source_id: int,
        data: SourceConfigUpdate,
    ) -> Awaitable[SourceConfigModel]: ...

    def update_headers_credentials(
        self, credentials: Mapping[int, dict[str, str]]
    ) -> Awaitable[Sequence[SourceConfigModel]]: ...

    def get_by_source_id(
        self, source_id: int
    ) -> Awaitable[SourceConfigModel]: ...

    def get_all(self) -> Awaitable[Sequence[SourceConfigModel]]: ...


class ISourceService(Protocol):
    def create(self, data: SourceCreate) -> Awaitable[SourceModel]: ...

    def update(
        self, id: int, data: SourceUpdate
    ) -> Awaitable[SourceModel]: ...

    def get_by_id(self, id: int) -> Awaitable[SourceModel]: ...

    def get_by_ids(
        self, ids: list[int]
    ) -> Awaitable[Sequence[SourceModel]]: ...

    def get_all(self) -> Awaitable[Sequence[SourceModel]]: ...

    def mark_failed(
        self,
        id: int,
        error: SourceErrorInfo,
    ) -> Awaitable[SourceModel]: ...

    def clear_error(self, id: int) -> Awaitable[SourceErrorRemoval]: ...

    def remove(self, id: int) -> Awaitable[SourceModel]: ...

    def get_batch(
        self,
        ids: list[int],
    ) -> Awaitable[BatchResultType[SourceModel, ValidationException]]: ...


class ISourceErrorService(Protocol):
    def apply_error(
        self, source_id: int, error: SourceErrorInfo | None
    ) -> Awaitable[SourceModel]: ...

    def apply_errors(
        self,
        errors: Mapping[int, SourceErrorInfo | None],
    ) -> Awaitable[Sequence[SourceModel]]: ...


class ISourceMetaService(Protocol):
    def build(
        self,
        source_ids: Sequence[int],
        symbol_ids: Sequence[int],
    ) -> Awaitable[SourcesMetaModel]: ...

    def build_by_sources(
        self,
        sources: Sequence[SourceModel],
        symbol_ids: Sequence[int],
    ) -> Awaitable[SourcesMetaModel]: ...

    def build_by_symbols(
        self,
        source_ids: Sequence[int],
        symbols: Sequence[SymbolModel],
    ) -> Awaitable[SourcesMetaModel]: ...

    def build_sources(
        self, source_ids: Sequence[int]
    ) -> Awaitable[SourceOnlyMetaModel]: ...


class ISourcePriceService(Protocol):
    def get_by_source_id(
        self, source_id: int
    ) -> Awaitable[SourcePricesResult]: ...

    def get_by_source_ids(
        self, source_ids: Sequence[int]
    ) -> Awaitable[MultiSourcePricesResult]: ...


class ICreateSource(Protocol):
    def execute(self, data: SourceCreate) -> Awaitable[SourceModel]: ...


class ISearchSources(Protocol):
    def execute(
        self, data: SourceSearch
    ) -> Awaitable[PagedType[SourceModel]]: ...


class IGetSourcesWithConfig(Protocol):
    def execute(
        self, switch: SourceSwitch | None = ...
    ) -> Awaitable[Sequence[SourceWithConfigModel]]: ...
