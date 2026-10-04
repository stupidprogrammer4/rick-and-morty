from papilio.infra.db.table import BaseTable
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from src.modules.content.drafts.domain.models import (
    DraftEvidenceModel,
    DraftModel,
)


class DraftTable(DraftModel, BaseTable, table=True):
    pass


class DraftEvidenceTable(DraftEvidenceModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("draft_id", "article_id"),
        ForeignKeyConstraint(["draft_id"], ["tbl_drafts.id"]),
        ForeignKeyConstraint(["article_id"], ["tbl_articles.id"]),
    )
