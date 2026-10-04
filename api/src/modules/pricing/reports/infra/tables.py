from papilio.infra.db.table import BaseTable

from src.modules.pricing.reports.domain.models import MarketSnapshotModel


class MarketSnapshotTable(MarketSnapshotModel, BaseTable, table=True):
    pass
