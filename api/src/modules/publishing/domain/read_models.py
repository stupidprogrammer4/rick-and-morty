from pydantic import BaseModel


class ChartParentReadModel(BaseModel):
    id: int
    owner_id: int
    bot_role: str
    channel_id: int
    status: str
    message_id: int | None
