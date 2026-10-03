from typing import Optional

from papilio.infra.db.table import BaseTable
from sqlalchemy.orm import Mapped
from sqlmodel import Relationship

from src.modules.pricing.sources.domain.models import (
    SourceConfigModel,
    SourceModel,
)


class SourceTable(SourceModel, BaseTable, table=True):
    config: Mapped[Optional["SourceConfigTable"]] = Relationship(
        back_populates="source",
        sa_relationship_kwargs={"uselist": False},
    )


class SourceConfigTable(SourceConfigModel, BaseTable, table=True):
    source: Mapped[Optional[SourceTable]] = Relationship(
        back_populates="config"
    )
