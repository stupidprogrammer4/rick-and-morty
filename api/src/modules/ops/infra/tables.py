from papilio.infra.db.table import BaseTable

from src.modules.ops.domain.models import PortalGuardModel


class PortalGuardTable(PortalGuardModel, BaseTable, table=True):
    pass
