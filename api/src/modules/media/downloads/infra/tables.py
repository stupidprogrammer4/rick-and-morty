from papilio.infra.db.table import BaseTable
from sqlalchemy import Index, UniqueConstraint

from src.modules.media.downloads.domain.models import (
    MediaItemModel,
    MediaJobModel,
)


class MediaJobTable(MediaJobModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("bot_id", "update_id"),
        Index("ix_media_jobs_due", "status", "id"),
        Index("ix_media_jobs_owner_status", "owner_id", "status"),
    )


class MediaItemTable(MediaItemModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("job_id", "position"),
        Index("ix_media_items_due", "job_id", "status", "position"),
        Index("ix_media_items_lease", "status", "lease_until"),
    )
