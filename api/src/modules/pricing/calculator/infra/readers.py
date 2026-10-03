from typing import Optional, Sequence

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlmodel import col, select

from src.modules.pricing.assets.domain.enums import (
    AggregationType,
    AssetCode,
)
from src.modules.pricing.assets.infra.tables import (
    AssetConfigTable,
    AssetSwitchTable,
    AssetTable,
)
from src.modules.pricing.bubbles.infra.tables import (
    BubbleConfigTable,
    BubbleTable,
)
from src.modules.pricing.calculator.domain.context import (
    AssetContext,
    BubbleContext,
    SwitchOrderContext,
    SymbolContext,
)
from src.modules.pricing.sources.domain.enums import SourceSwitch
from src.modules.pricing.sources.infra.tables import SourceTable
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.infra.tables import SymbolTable


class SymbolReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def get_all(
        self,
        excludes: Sequence[AssetCode] = (),
    ) -> Sequence[SymbolContext]:
        """
        Desc: Read every symbol together with the asset it belongs to.
        Args:
            excludes (Sequence[AssetCode]): Asset codes to leave out.
        Returns:
            return (Sequence[SymbolContext]): Symbol rows by ID.
        """
        stmt = (
            select(
                SymbolTable.id,
                SymbolTable.code,
                SymbolTable.asset_id,
                col(AssetTable.code).label("asset_code"),
            )
            .join(AssetTable, col(AssetTable.id) == col(SymbolTable.asset_id))
            .where(col(AssetTable.code).not_in(excludes))
            .order_by(col(SymbolTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            SymbolContext(
                id=id,
                code=AssetCode(asset_code),
                symbol=SymbolCode(code),
                asset_id=asset_id,
            )
            for id, code, asset_id, asset_code in rows
        ]

    async def get_symbols_of_asset(
        self,
        asset_id: int,
    ) -> Sequence[SymbolContext]:
        """
        Desc: Read the symbols that belong to one asset.
        Args:
            asset_id (int): ID of the asset to read symbols for.
        Returns:
            return (Sequence[SymbolContext]): Symbol rows by ID.
        """
        stmt = (
            select(
                SymbolTable.id,
                SymbolTable.code,
                SymbolTable.asset_id,
                col(AssetTable.code).label("asset_code"),
            )
            .join(AssetTable, col(AssetTable.id) == col(SymbolTable.asset_id))
            .where(col(SymbolTable.asset_id) == asset_id)
            .order_by(col(SymbolTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            SymbolContext(
                id=id,
                code=AssetCode(asset_code),
                symbol=SymbolCode(code),
                asset_id=asset_id,
            )
            for id, code, asset_id, asset_code in rows
        ]


class AssetReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def get_all_config(
        self,
        excludes: Sequence[AssetCode] = (),
    ) -> Sequence[AssetContext]:
        """
        Desc: Read every asset together with its aggregation rule.
        Args:
            excludes (Sequence[AssetCode]): Asset codes to leave out.
        Returns:
            return (Sequence[AssetContext]): Asset rows by ID.
        """
        stmt = (
            select(
                AssetTable.id,
                AssetTable.code,
                AssetConfigTable.agg_type,
            )
            .join(
                AssetConfigTable,
                col(AssetConfigTable.asset_id) == col(AssetTable.id),
            )
            .where(col(AssetTable.code).not_in(excludes))
            .order_by(col(AssetTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            AssetContext(
                code=AssetCode(code),
                asset_id=id,
                agg_type=AggregationType(agg_type),
            )
            for id, code, agg_type in rows
        ]

    async def get_id_by_code(self, code: AssetCode) -> Optional[int]:
        """
        Desc: Get the ID of the asset carrying this code.
        Args:
            code (AssetCode): Code of the asset to look up.
        Returns:
            return (Optional[int]): Found asset ID or None.
        """
        stmt = select(AssetTable.id).where(col(AssetTable.code) == code)
        result = await self.uow.execute(stmt)
        found = result.scalar_one_or_none()
        return found

    async def get_asset_config(
        self,
        asset_id: int,
    ) -> Optional[AssetContext]:
        """
        Desc: Read one asset together with its aggregation rule.
        Args:
            asset_id (int): ID of the asset to read.
        Returns:
            return (Optional[AssetContext]): Found asset or None.
        """
        stmt = (
            select(
                AssetTable.id,
                AssetTable.code,
                AssetConfigTable.agg_type,
            )
            .join(
                AssetConfigTable,
                col(AssetConfigTable.asset_id) == col(AssetTable.id),
            )
            .where(col(AssetTable.id) == asset_id)
        )
        result = await self.uow.execute(stmt)
        row = result.first()
        context = None
        if row is not None:
            id, code, agg_type = row
            context = AssetContext(
                code=AssetCode(code),
                asset_id=id,
                agg_type=AggregationType(agg_type),
            )
        return context


class BubbleReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def get_all(self) -> Sequence[BubbleContext]:
        """
        Desc: Read every bubble together with its aggregation rule.
        Returns:
            return (Sequence[BubbleContext]): Bubble rows by ID.
        """
        stmt = (
            select(
                BubbleTable.id,
                BubbleTable.code,
                BubbleConfigTable.agg_type,
                col(AssetTable.id).label("asset_id"),
            )
            .join(AssetTable, col(AssetTable.code) == col(BubbleTable.code))
            .join(
                BubbleConfigTable,
                col(BubbleConfigTable.bubble_id) == col(BubbleTable.id),
            )
            .order_by(col(BubbleTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            BubbleContext(
                code=AssetCode(code),
                bubble_id=id,
                asset_id=asset_id,
                agg_type=AggregationType(agg_type),
            )
            for id, code, agg_type, asset_id in rows
        ]

    async def get_bubble_config(
        self,
        bubble_id: int,
    ) -> Optional[BubbleContext]:
        """
        Desc: Read one bubble together with its aggregation rule.
        Args:
            bubble_id (int): ID of the bubble to read.
        Returns:
            return (Optional[BubbleContext]): Found bubble or None.
        """
        stmt = (
            select(
                BubbleTable.id,
                BubbleTable.code,
                BubbleConfigTable.agg_type,
                col(AssetTable.id).label("asset_id"),
            )
            .join(AssetTable, col(AssetTable.code) == col(BubbleTable.code))
            .join(
                BubbleConfigTable,
                col(BubbleConfigTable.bubble_id) == col(BubbleTable.id),
            )
            .where(col(BubbleTable.id) == bubble_id)
        )
        result = await self.uow.execute(stmt)
        row = result.first()
        context = None
        if row is not None:
            id, code, agg_type, asset_id = row
            context = BubbleContext(
                code=AssetCode(code),
                bubble_id=id,
                asset_id=asset_id,
                agg_type=AggregationType(agg_type),
            )
        return context


class SwitchOrderReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def get_switch_order(
        self,
        asset_id: int,
    ) -> Sequence[SwitchOrderContext]:
        """
        Desc: Read the order of switches one asset is priced through.
        Args:
            asset_id (int): ID of the asset to read the order for.
        Returns:
            return (Sequence[SwitchOrderContext]): Switches by priority.
        """
        stmt = (
            select(
                AssetSwitchTable.asset_id,
                AssetSwitchTable.switch,
                AssetSwitchTable.priority,
                AssetTable.code,
            )
            .join(
                AssetTable,
                col(AssetTable.id) == col(AssetSwitchTable.asset_id),
            )
            .where(col(AssetSwitchTable.asset_id) == asset_id)
            .order_by(
                col(AssetSwitchTable.priority),
                col(AssetSwitchTable.id),
            )
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            SwitchOrderContext(
                code=AssetCode(code),
                asset_id=asset_id,
                switch=SourceSwitch(switch),
                order=priority,
            )
            for asset_id, switch, priority, code in rows
        ]

    async def get_all(
        self,
        excludes: Sequence[AssetCode] = (),
    ) -> Sequence[SwitchOrderContext]:
        """
        Desc: Read the order of switches every asset is priced through.
        Args:
            excludes (Sequence[AssetCode]): Asset codes to leave out.
        Returns:
            return (Sequence[SwitchOrderContext]): Switches by priority.
        """
        stmt = (
            select(
                AssetSwitchTable.asset_id,
                AssetSwitchTable.switch,
                AssetSwitchTable.priority,
                AssetTable.code,
            )
            .join(
                AssetTable,
                col(AssetTable.id) == col(AssetSwitchTable.asset_id),
            )
            .where(col(AssetTable.code).not_in(excludes))
            .order_by(
                col(AssetSwitchTable.asset_id),
                col(AssetSwitchTable.priority),
                col(AssetSwitchTable.id),
            )
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            SwitchOrderContext(
                code=AssetCode(code),
                asset_id=asset_id,
                switch=SourceSwitch(switch),
                order=priority,
            )
            for asset_id, switch, priority, code in rows
        ]


class SourceReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def get_source_switches(
        self,
    ) -> Sequence[tuple[int, SourceSwitch]]:
        """
        Desc: Read which switch each source is read through.
        Returns:
            return (Sequence[tuple[int, SourceSwitch]]): Source and switch.
        """
        stmt = select(SourceTable.id, SourceTable.source_type).order_by(
            col(SourceTable.id)
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [(id, SourceSwitch(switch)) for id, switch in rows]
