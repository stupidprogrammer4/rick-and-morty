from papilio.infra.db.table import BaseTable
from sqlalchemy import ForeignKeyConstraint, Index

from src.modules.publishing.domain.models import (
    PrivateReplyModel,
    PublicationModel,
)


class PublicationTable(PublicationModel, BaseTable, table=True):
    __table_args__ = (
        ForeignKeyConstraint(["draft_id"], ["tbl_drafts.id"]),
        Index("ix_publications_due", "status", "scheduled_at", "id"),
        Index("ix_publications_budget", "budget_day", "status"),
    )


class PrivateReplyTable(PrivateReplyModel, BaseTable, table=True):
    __table_args__ = (
        Index("ix_private_replies_due", "status", "scheduled_at", "id"),
    )
