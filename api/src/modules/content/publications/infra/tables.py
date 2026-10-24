from datetime import datetime

from papilio.infra.db.table import BaseTable
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT
from sqlmodel import Field

from src.modules.content.publications.domain.models import (
    PublicationChartModel,
    PublicationModel,
)


class PublicationTable(PublicationModel, BaseTable, table=True):
    scheduled_at: datetime = Field(  # pyright: ignore[reportGeneralTypeIssues]
        sa_column=Column(
            DateTime(timezone=True).with_variant(DATETIME(fsp=6), "mysql"),
            nullable=False,
            index=True,
        )
    )
    __table_args__ = (
        ForeignKeyConstraint(["draft_id"], ["tbl_drafts.id"]),
        Index("ix_publications_due", "status", "scheduled_at", "id"),
        Index("ix_publications_budget", "budget_day", "status"),
    )


class PublicationChartTable(PublicationChartModel, BaseTable, table=True):
    payload: str = Field(  # pyright: ignore[reportGeneralTypeIssues]
        sa_column=Column(
            Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False
        )
    )
    scheduled_at: datetime = Field(  # pyright: ignore[reportGeneralTypeIssues]
        sa_column=Column(
            DateTime(timezone=True).with_variant(DATETIME(fsp=6), "mysql"),
            nullable=False,
        )
    )
    __table_args__ = (
        UniqueConstraint("publication_id", "asset_id"),
        UniqueConstraint(
            "publication_id", "gallery_key", name="uq_chart_gallery"
        ),
        Index("ix_publication_charts_due", "status", "scheduled_at", "id"),
    )
