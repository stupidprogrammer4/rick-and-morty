from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

from portal_contracts.enums import BotRole, Category


class DraftCreate(BaseModel):
    category: Category
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=4000)
    publisher_bot: BotRole


class DraftEdit(BaseModel):
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=4000)


class DraftDecision(BaseModel):
    revision: int = Field(ge=1)
    origin_bot: BotRole


class DraftOut(BaseModel):
    id: int
    owner_id: int
    origin_bot: BotRole
    category: Category
    title: str
    text: str
    revision: int
    status: str
    publisher_bot: BotRole
    synthetic: bool


class DraftPage(BaseModel):
    items: list[DraftOut]
    total: int
    page: int
    per_page: int


class PublishRequest(DraftDecision):
    scheduled_at: AwareDatetime | None = None


class PublicationOut(BaseModel):
    id: int
    draft_id: int
    revision: int
    bot_role: BotRole
    status: str
    scheduled_at: datetime
    message_id: int | None
    failure_reason: str | None


class PublicationResolution(BaseModel):
    message_id: int | None = Field(default=None, gt=0)
    resend: bool = False


class PauseChange(BaseModel):
    paused: bool
