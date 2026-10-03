from typing import Optional

from papilio.infra.db.table import BaseTable
from sqlalchemy.orm import Mapped
from sqlmodel import Relationship

from src.modules.pricing.bubbles.domain.models import (
    BubbleConfigModel,
    BubbleModel,
)


class BubbleTable(BubbleModel, BaseTable, table=True):
    config: Mapped[Optional["BubbleConfigTable"]] = Relationship(
        back_populates="bubble",
        sa_relationship_kwargs={"uselist": False},
    )


class BubbleConfigTable(BubbleConfigModel, BaseTable, table=True):
    bubble: Optional[BubbleTable] = Relationship(back_populates="config")
