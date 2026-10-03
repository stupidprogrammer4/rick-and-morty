from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

from portal_contracts.enums import BotRole, Category
from portal_contracts.telegram import PublicationNavigation


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


class PublicationPage(BaseModel):
    title: str
    text: str = Field(min_length=1, max_length=4000)


class PublicationPages(BaseModel):
    items: list[PublicationPage] = Field(min_length=1, max_length=100)
    previous_label: str
    next_label: str
    page_label: str

    def navigation(
        self, publication_id: int, page: int
    ) -> PublicationNavigation:
        return PublicationNavigation(
            publication_id=publication_id,
            page=page,
            total=len(self.items),
            previous_label=self.previous_label,
            next_label=self.next_label,
            page_label=self.page_label,
        )


class PublishedPage(BaseModel):
    role: BotRole
    chat_id: int
    message_id: int
    text: str
    navigation: PublicationNavigation


class PublicationChartOut(BaseModel):
    id: int
    publication_id: int
    asset_id: int
    status: str
    message_id: int | None
    failure_reason: str | None


class PauseChange(BaseModel):
    paused: bool
