from papilio.infra.db.table import BaseTable

from src.modules.ops.guards.domain.models import PortalGuardModel


class PortalGuardTable(PortalGuardModel, BaseTable, table=True):
    pass
