from typing import Any, Mapping, Sequence

from papilio.infra.db.tools.read import fetch_page
from papilio.infra.db.uow import MySQLUnitOfWork
from papilio.schemas.results import PagedType
from papilio.types.enums import SortOrder
from sqlalchemy import ColumnElement
from sqlalchemy.orm import joinedload
from sqlmodel import col, select

from src.modules.pricing.sources.domain.enums import (
    SourceSortBy,
    SourceSwitch,
    SourceUpdateType,
)
from src.modules.pricing.sources.domain.models import (
    SourceModel,
    SourceWithConfigModel,
)
from src.modules.pricing.sources.infra.tables import (
    SourceTable,
)


class SourceReader:
    sortables: Mapping[SourceSortBy, Any] = {
        SourceSortBy.CREATED_AT: col(SourceTable.created_at),
        SourceSortBy.TITLE: col(SourceTable.title),
    }

    def __init__(self, uow: MySQLUnitOfWork) -> None:
        self.uow = uow

    async def search(
        self,
        q: str | None,
        source_types: Sequence[SourceSwitch] | None,
        update_types: Sequence[SourceUpdateType] | None,
        is_active: bool | None,
        has_error: bool | None,
        sort_by: SourceSortBy,
        sort_order: SortOrder,
        offset: int,
        limit: int,
        id_match: int | None = None,
    ) -> PagedType[SourceModel]:
        """Read the filtered, ordered source page and its total."""
        clauses: list[ColumnElement[bool]] = []
        if q is not None:
            pattern = f"%{q}%"
            clause = col(SourceTable.title).ilike(pattern) | col(
                SourceTable.code
            ).ilike(pattern)
            if id_match is not None:
                clause = clause | (col(SourceTable.id) == id_match)
            clauses.append(clause)
        if source_types:
            clauses.append(col(SourceTable.source_type).in_(source_types))
        if update_types:
            clauses.append(col(SourceTable.update_type).in_(update_types))
        if is_active is not None:
            clauses.append(col(SourceTable.is_active).is_(is_active))
        if has_error is not None:
            clauses.append(
                col(SourceTable.error).isnot(None)
                if has_error
                else col(SourceTable.error).is_(None)
            )
        column = self.sortables[sort_by]
        ordered = (
            column.asc() if sort_order is SortOrder.ASC else column.desc()
        )
        stmt = (
            select(SourceTable)
            .where(*clauses)
            .order_by(ordered, col(SourceTable.id).desc())
        )
        paged = await fetch_page(self.uow, stmt, offset=offset, limit=limit)
        return paged

    async def get_with_config(
        self,
        switch: SourceSwitch | None = None,
        update_types: Sequence[SourceUpdateType] | None = None,
        is_active: bool | None = None,
    ) -> Sequence[SourceWithConfigModel]:
        """Read matching sources and their configs in one query."""
        stmt = (
            select(SourceTable)
            .options(joinedload(SourceTable.config, innerjoin=True))
            .order_by(col(SourceTable.id))
        )
        if switch is not None:
            stmt = stmt.where(col(SourceTable.source_type) == switch)
        if update_types is not None:
            stmt = stmt.where(col(SourceTable.update_type).in_(update_types))
        if is_active is not None:
            stmt = stmt.where(col(SourceTable.is_active).is_(is_active))
        result = await self.uow.execute(stmt)
        return [
            SourceWithConfigModel(**row.to_dict(), config=row.config)
            for row in result.unique().scalars().all()
        ]
