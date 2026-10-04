from datetime import datetime
from zoneinfo import ZoneInfo

from portal_contracts.configuration import EffectivePortalPolicy


class PublicationPolicy:
    def __init__(self, settings: EffectivePortalPolicy):
        self.settings = settings

    def quiet(self, now: datetime) -> bool:
        local = now.astimezone(ZoneInfo(self.settings.timezone)).time()
        start = self.settings.quiet_start
        end = self.settings.quiet_end
        if start == end:
            return False
        if start > end:
            return local >= start or local < end
        return start <= local < end
