from typing import Sequence

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import select as sa_select
from sqlmodel import col, select

from src.modules.pricing.assets.infra.tables import AssetTable
from src.modules.pricing.engine.domain.context import (
    AssetRefContext,
    SourceContext,
    SymbolRefContext,
)
from src.modules.pricing.sources.domain.enums import (
    SourceCode,
    SourceSwitch,
    SourceUpdateType,
)
from src.modules.pricing.sources.infra.tables import (
    SourceConfigTable,
    SourceTable,
)
from src.modules.pricing.symbols.infra.tables import SymbolTable


class AssetReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def read_refs(self) -> Sequence[AssetRefContext]:
        """
        Desc: Read the ID and code of every asset.
        Returns:
            return (Sequence[AssetRefContext]): Asset references by ID.
        """
        stmt = select(AssetTable.id, AssetTable.code).order_by(
            col(AssetTable.id)
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [AssetRefContext(code=code, id=id) for id, code in rows]


class SourceReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def read_all(
        self,
        update_types: Sequence[SourceUpdateType] | None = None,
        is_active: bool | None = None,
    ) -> Sequence[SourceContext]:
        """
        Desc: Read the sources a crawl may run against.
        Args:
            update_types (Sequence[SourceUpdateType] | None): Kinds to keep.
            is_active (bool | None): Active state to filter by, or None.
        Returns:
            return (Sequence[SourceContext]): Source rows by ID.
        """
        stmt = (
            sa_select(
                col(SourceTable.id),
                col(SourceTable.code),
                col(SourceTable.source_type),
                col(SourceConfigTable.timeout),
                col(SourceConfigTable.headers_credentials),
                col(SourceConfigTable.fetchers),
            )
            .join(
                SourceConfigTable,
                col(SourceConfigTable.source_id) == col(SourceTable.id),
            )
            .order_by(col(SourceTable.id))
        )
        if update_types is not None:
            stmt = stmt.where(
                col(SourceTable.update_type).in_(list(update_types))
            )
        if is_active is not None:
            stmt = stmt.where(col(SourceTable.is_active).is_(is_active))
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            SourceContext(
                code=SourceCode(code),
                id=id,
                switch=SourceSwitch(switch),
                timeout=timeout,
                headers_credentials=headers,
                fetchers=fetchers,
            )
            for id, code, switch, timeout, headers, fetchers in rows
        ]

    async def get_by_code_and_active(
        self,
        code: SourceCode,
        *,
        is_active: bool,
    ) -> SourceContext | None:
        """
        Desc: Read one active source by its code.
        Args:
            code (SourceCode): Code of the source to read.
        Returns:
            return (SourceContext | None): Found source or None.
        """
        stmt = (
            sa_select(
                col(SourceTable.id),
                col(SourceTable.code),
                col(SourceTable.source_type),
                col(SourceConfigTable.timeout),
                col(SourceConfigTable.headers_credentials),
                col(SourceConfigTable.fetchers),
                col(SourceTable.error),
            )
            .join(
                SourceConfigTable,
                col(SourceConfigTable.source_id) == col(SourceTable.id),
            )
            .where(col(SourceTable.code) == code)
            .where(col(SourceTable.is_active).is_(is_active))
        )
        result = await self.uow.execute(stmt)
        row = result.first()
        if row is None:
            return None
        id, code, switch, timeout, headers, fetchers, error = row
        return SourceContext(
            code=SourceCode(code),
            id=id,
            switch=SourceSwitch(switch),
            timeout=timeout,
            headers_credentials=headers,
            fetchers=fetchers,
            has_error=error is not None,
        )

    async def read_by_switch(
        self,
        switch: SourceSwitch,
    ) -> Sequence[SourceContext]:
        """
        Desc: Read the active sources read through one switch.
        Args:
            switch (SourceSwitch): Switch the sources are read through.
        Returns:
            return (Sequence[SourceContext]): Source rows by ID.
        """
        stmt = (
            sa_select(
                col(SourceTable.id),
                col(SourceTable.code),
                col(SourceTable.source_type),
                col(SourceConfigTable.timeout),
                col(SourceConfigTable.headers_credentials),
                col(SourceConfigTable.fetchers),
            )
            .join(
                SourceConfigTable,
                col(SourceConfigTable.source_id) == col(SourceTable.id),
            )
            .where(col(SourceTable.source_type) == switch)
            .order_by(col(SourceTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            SourceContext(
                code=SourceCode(code),
                id=id,
                switch=SourceSwitch(switch),
                timeout=timeout,
                headers_credentials=headers,
                fetchers=fetchers,
            )
            for id, code, switch, timeout, headers, fetchers in rows
        ]


class SymbolReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def read_refs(self) -> Sequence[SymbolRefContext]:
        """
        Desc: Read the ID and code of every symbol.
        Returns:
            return (Sequence[SymbolRefContext]): Symbol references by ID.
        """
        stmt = select(SymbolTable.id, SymbolTable.code).order_by(
            col(SymbolTable.id)
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [SymbolRefContext(code=code, id=id) for id, code in rows]
