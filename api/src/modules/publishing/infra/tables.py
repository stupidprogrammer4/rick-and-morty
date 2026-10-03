from datetime import datetime

from papilio.infra.db.table import BaseTable
from sqlalchemy import Column, DateTime, ForeignKeyConstraint, Index
from sqlalchemy.dialects.mysql import DATETIME
from sqlmodel import Field

from src.modules.publishing.domain.models import (
    PrivateReplyModel,
    PublicationModel,
)
from src.shared.dates import utc_now


class PublicationTable(PublicationModel, BaseTable, table=True):
    scheduled_at: datetime = Field(
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


class PrivateReplyTable(PrivateReplyModel, BaseTable, table=True):
    scheduled_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True).with_variant(DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
    )
    __table_args__ = (
        Index("ix_private_replies_due", "status", "scheduled_at", "id"),
    )
