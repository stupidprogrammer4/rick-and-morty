from typing import Sequence

from papilio.errors.exceptions import ValidationException
from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional
from papilio.schemas.results import BatchResultType
from papilio.tools.checks import IDChecks

from src.modules.pricing.symbols.domain.dtos import SymbolCreate, SymbolUpdate
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.domain.models import (
    SymbolMetaModel,
    SymbolModel,
    SymbolsMetaModel,
)
from src.modules.pricing.symbols.infra.mysql import SymbolRepository
from src.modules.pricing.symbols.interfaces import ISymbolService


class SymbolService(IDChecks[SymbolModel]):
    entity = "Symbol"

    def __init__(self, repo: SymbolRepository) -> None:
        self.repo = repo

    @handle_conflicts
    @transactional
    async def create(self, data: SymbolCreate) -> SymbolModel:
        """
        Desc: Create a symbol.
        Args:
            data (SymbolCreate): Validated payload to persist.
        Returns:
            return (SymbolModel): The created symbol.
        """
        symbol = await self.repo.create(
            SymbolModel(**data.to_row(exclude_unset=False))
        )
        return symbol

    @handle_conflicts
    @transactional
    async def update(self, id: int, data: SymbolUpdate) -> SymbolModel:
        """
        Desc: Patch a symbol by id.
        Args:
            id (int): ID of the symbol.
            data (SymbolUpdate): The fields to change.
        Returns:
            return (SymbolModel): The updated symbol.
        """
        row = self._check_not_empty_dict(data.to_row())
        await self.repo.update_by_id(id, row)
        symbol = await self.repo.get_by_id(id)
        symbol = self._check_for_id_existence(id, symbol)
        return symbol

    async def get_by_id(self, id: int) -> SymbolModel:
        """
        Desc: Get a symbol by id.
        Args:
            id (int): ID of the symbol.
        Returns:
            return (SymbolModel): The found symbol.
        """
        symbol = await self.repo.get_by_id(id)
        symbol = self._check_for_id_existence(id, symbol)
        return symbol

    async def get_by_ids(
        self,
        ids: list[int],
    ) -> Sequence[SymbolModel]:
        """
        Desc: Get the symbols the given ids belong to.
        Args:
            ids (list[int]): IDs of the symbols to read.
        Returns:
            return (Sequence[SymbolModel]): The symbols that exist.
        """
        symbols = await self.repo.get_by_ids(ids)
        return symbols

    async def get_all(self) -> Sequence[SymbolModel]:
        """
        Desc: Get every symbol.
        Returns:
            return (Sequence[SymbolModel]): All symbols.
        """
        symbols = await self.repo.get_all()
        return symbols

    async def get_by_code(self, code: SymbolCode) -> SymbolModel:
        """
        Desc: Get one symbol by its code.
        Args:
            code (SymbolCode): The symbol's code.
        Returns:
            return (SymbolModel): The found symbol.
        """
        symbol = await self.repo.get_by_code(code)
        symbol = self._check_for_existence("code", code, symbol)
        return symbol

    async def get_by_asset_id(
        self,
        asset_id: int,
    ) -> Sequence[SymbolModel]:
        """
        Desc: Get every symbol an asset is quoted through.
        Args:
            asset_id (int): ID of the owning asset.
        Returns:
            return (Sequence[SymbolModel]): The asset's symbols.
        """
        symbols = await self.repo.get_by_asset_id(asset_id)
        return symbols

    @handle_conflicts
    @transactional
    async def remove(self, id: int) -> SymbolModel:
        """
        Desc: Delete a symbol by id.
        Args:
            id (int): ID of the symbol.
        Returns:
            return (SymbolModel): The deleted symbol.
        """
        symbol = await self.repo.get_by_id(id)
        await self.repo.remove_by_id(id)
        symbol = self._check_for_id_existence(id, symbol)
        return symbol

    async def get_batch(
        self,
        ids: list[int],
    ) -> BatchResultType[SymbolModel, ValidationException]:
        """
        Desc: Get many symbols at once, saying which of the ids nothing
            answered to.
        Args:
            ids (list[int]): IDs of the symbols.
        Returns:
            return (BatchResultType): What was found, and an error per id
                that was not.
        """
        found = await self.repo.get_by_ids(ids)
        batch = self._check_batch_data(ids, found)
        return batch


class SymbolMetaService:
    def __init__(self, symbols: ISymbolService) -> None:
        self.symbols = symbols

    async def build(self, symbol_ids: Sequence[int]) -> SymbolsMetaModel:
        """
        Desc: Name the lines the given ids belong to.
        Args:
            symbol_ids (Sequence[int]): IDs of the lines to name.
        Returns:
            return (SymbolsMetaModel): One entry per line that exists.
        """
        symbols = await self.symbols.get_by_ids(list(symbol_ids))
        return SymbolsMetaModel(symbols=SymbolMetaModel.from_objs(symbols))
