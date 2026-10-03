from typing import Optional, Sequence

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlmodel import col, select

from src.modules.pricing.logins.domain.context import LoginContext
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.sources.infra.tables import (
    SourceConfigTable,
    SourceTable,
)


class LoginReader(MySQLReader):
    def __init__(self, uow: MySQLUnitOfWork):
        super().__init__(uow)

    async def read_by_codes(
        self,
        codes: Sequence[SourceCode],
    ) -> Sequence[LoginContext]:
        """
        Desc: Read the sign-in details of the sources holding some.
        Args:
            codes (Sequence[SourceCode]): Codes of the sources to read.
        Returns:
            return (Sequence[LoginContext]): Sign-in rows by source ID.
        """
        stmt = (
            select(
                SourceTable.id,
                SourceTable.code,
                SourceConfigTable.auth_credentials,
                SourceConfigTable.login,
            )
            .join(
                SourceConfigTable,
                col(SourceConfigTable.source_id) == col(SourceTable.id),
            )
            .where(
                col(SourceTable.code).in_(codes),
                col(SourceConfigTable.auth_credentials).isnot(None),
            )
            .order_by(col(SourceTable.id))
        )
        result = await self.uow.execute(stmt)
        rows = result.all()
        return [
            LoginContext(
                code=code, id=id, auth_credentials=secret, login=login
            )
            for id, code, secret, login in rows
        ]

    async def read_by_code(
        self,
        code: SourceCode,
    ) -> Optional[LoginContext]:
        """
        Desc: Read the sign-in details of one source by its code.
        Args:
            code (SourceCode): Code of the source to read.
        Returns:
            return (Optional[LoginContext]): Found sign-in row or None.
        """
        stmt = (
            select(
                SourceTable.id,
                SourceTable.code,
                SourceConfigTable.auth_credentials,
                SourceConfigTable.login,
            )
            .join(
                SourceConfigTable,
                col(SourceConfigTable.source_id) == col(SourceTable.id),
            )
            .where(
                col(SourceTable.code) == code,
                col(SourceConfigTable.auth_credentials).isnot(None),
            )
        )
        result = await self.uow.execute(stmt)
        row = result.first()
        context = None
        if row is not None:
            id, found, secret, login = row
            context = LoginContext(
                code=found, id=id, auth_credentials=secret, login=login
            )
        return context

    async def read(self, source_id: int) -> Optional[LoginContext]:
        """
        Desc: Read the sign-in details of one source by its ID.
        Args:
            source_id (int): ID of the source to read.
        Returns:
            return (Optional[LoginContext]): Found sign-in row or None.
        """
        stmt = (
            select(
                SourceTable.id,
                SourceTable.code,
                SourceConfigTable.auth_credentials,
                SourceConfigTable.login,
            )
            .join(
                SourceConfigTable,
                col(SourceConfigTable.source_id) == col(SourceTable.id),
            )
            .where(
                col(SourceTable.id) == source_id,
                col(SourceConfigTable.auth_credentials).isnot(None),
            )
        )
        result = await self.uow.execute(stmt)
        row = result.first()
        context = None
        if row is not None:
            id, code, secret, login = row
            context = LoginContext(
                code=code, id=id, auth_credentials=secret, login=login
            )
        return context
