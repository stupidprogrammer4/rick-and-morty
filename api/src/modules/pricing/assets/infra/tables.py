from typing import Optional

from papilio.infra.db.table import BaseTable
from sqlalchemy.orm import Mapped
from sqlmodel import Relationship, UniqueConstraint

from src.modules.pricing.assets.domain.models import (
    AssetConfigModel,
    AssetModel,
    AssetSwitchModel,
)


class AssetTable(AssetModel, BaseTable, table=True):
    config: Mapped[Optional["AssetConfigTable"]] = Relationship(
        back_populates="asset",
        sa_relationship_kwargs={"uselist": False},
    )


class AssetConfigTable(AssetConfigModel, BaseTable, table=True):
    asset: Optional[AssetTable] = Relationship(back_populates="config")


class AssetSwitchTable(AssetSwitchModel, BaseTable, table=True):
    __table_args__ = (UniqueConstraint("asset_id", "switch"),)
