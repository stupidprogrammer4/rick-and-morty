from papilio.infra.db.table import BaseTable
from sqlalchemy import Index, UniqueConstraint

from src.modules.media.library.domain.models import MediaAssetModel


class MediaAssetTable(MediaAssetModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("cache_key"),
        Index("ix_media_assets_expires", "expires_at"),
    )
