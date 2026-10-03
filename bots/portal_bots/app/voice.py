from portal_contracts.enums import BotRole
from portal_contracts.presentation import PortalPresentation


class BotVoice:
    def __init__(self, presentation: PortalPresentation):
        self.presentation = presentation

    def accepted(self, role: BotRole, id: int) -> str:
        return self.presentation.voices[role].accepted.format(id=id)

    def welcome(self, role: BotRole) -> str:
        return self.presentation.voices[role].welcome

    def error(self, role: BotRole, detail: str) -> str:
        return self.presentation.voices[role].error.format(detail=detail)
