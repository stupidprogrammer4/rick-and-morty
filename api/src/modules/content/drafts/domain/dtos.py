from pydantic import BaseModel

from portal_contracts.enums import BotRole


class MarketDraftContext(BaseModel):
    id: int
    owner_id: int
    origin_bot: BotRole
