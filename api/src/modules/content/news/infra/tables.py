from papilio.infra.db.table import BaseTable
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from src.modules.content.news.domain.models import ArticleModel


class ArticleTable(ArticleModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("mission_id", "url_hash"),
        ForeignKeyConstraint(["mission_id"], ["tbl_missions.id"]),
    )
