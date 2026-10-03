from typing import Optional, Sequence

from papilio.infra.db.repositories.backends.mysql import (
    MySQLIdentifiedRepository,
)
from sqlmodel import col, select

from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.domain.models import SymbolModel
from src.modules.pricing.symbols.infra.tables import SymbolTable


class SymbolRepository(MySQLIdentifiedRepository[SymbolModel]):
    table = SymbolTable

    async def get_by_id(self, id: int) -> SymbolModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: SymbolCode) -> Optional[SymbolModel]:
        """
        Desc: Get one symbol by its code.
        Args:
            code (SymbolCode): The symbol's code.
        Returns:
            return (Optional[SymbolModel]): The symbol, or None.
        """
        stmt = select(SymbolTable).where(col(SymbolTable.code) == code)
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_asset_id(
        self,
        asset_id: int,
    ) -> Sequence[SymbolModel]:
        """
        Desc: Get every symbol of one asset, oldest first.
        Args:
            asset_id (int): ID of the owning asset.
        Returns:
            return (Sequence[SymbolModel]): The asset's symbols.
        """
        stmt = (
            select(SymbolTable)
            .where(col(SymbolTable.asset_id) == asset_id)
            .order_by(col(SymbolTable.id))
        )
        result = await self.uow.execute(stmt)
        return result.scalars().all()
