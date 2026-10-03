from collections.abc import Awaitable
from typing import Protocol, Sequence

from papilio.errors.exceptions import ValidationException
from papilio.schemas.results import BatchResultType

from src.modules.pricing.symbols.domain.dtos import SymbolCreate, SymbolUpdate
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.domain.models import (
    SymbolModel,
    SymbolsMetaModel,
)


class ISymbolService(Protocol):
    def create(self, data: SymbolCreate) -> Awaitable[SymbolModel]: ...

    def update(
        self, id: int, data: SymbolUpdate
    ) -> Awaitable[SymbolModel]: ...

    def get_by_id(self, id: int) -> Awaitable[SymbolModel]: ...

    def get_by_ids(
        self, ids: list[int]
    ) -> Awaitable[Sequence[SymbolModel]]: ...

    def get_all(self) -> Awaitable[Sequence[SymbolModel]]: ...

    def get_by_code(self, code: SymbolCode) -> Awaitable[SymbolModel]: ...

    def get_by_asset_id(
        self,
        asset_id: int,
    ) -> Awaitable[Sequence[SymbolModel]]: ...

    def remove(self, id: int) -> Awaitable[SymbolModel]: ...

    def get_batch(
        self,
        ids: list[int],
    ) -> Awaitable[BatchResultType[SymbolModel, ValidationException]]: ...


class ISymbolMetaService(Protocol):
    def build(
        self, symbol_ids: Sequence[int]
    ) -> Awaitable[SymbolsMetaModel]: ...
