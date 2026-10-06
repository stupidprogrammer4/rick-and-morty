import base64
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from portal_contracts.enums import BotRole


class ReactionEmoji(StrEnum):
    SEEN = "👀"
    THINKING = "🤔"
    AWESOME = "🔥"
    SURPRISED = "🤯"
    LIKE = "👍"
    SAD = "😢"
    CODE = "👨‍💻"


class PublicationNavigation(BaseModel):
    publication_id: int = Field(gt=0)
    page: int = Field(ge=0)
    total: int = Field(ge=1, le=100)
    previous_label: str
    next_label: str
    page_label: str

    @model_validator(mode="after")
    def page_exists(self):
        if self.page >= self.total:
            raise ValueError("Page is outside the publication")
        return self


class TelegramDelivery(BaseModel):
    role: BotRole
    chat_id: int
    text: str = Field(min_length=1, max_length=4096)
    publication_id: int | None = None
    draft_id: int | None = None
    revision: int | None = None
    navigation: PublicationNavigation | None = None
    png_base64: str | None = Field(default=None, max_length=350000)

    @field_validator("png_base64")
    @classmethod
    def valid_png(cls, value: str | None) -> str | None:
        return bounded_png(value) if value is not None else None

    @model_validator(mode="after")
    def publication_photo(self):
        if self.png_base64 is not None and (
            self.publication_id is None
            or self.draft_id is not None
            or self.navigation is not None
        ):
            raise ValueError(
                "Post photos require a publication without buttons"
            )
        return self


class TelegramPhotoDelivery(BaseModel):
    role: BotRole
    chat_id: int
    publication_id: int = Field(gt=0)
    chart_id: int = Field(gt=0)
    reply_to_message_id: int = Field(gt=0)
    caption: str = Field(max_length=1024)
    png_base64: str = Field(max_length=350000)

    @field_validator("png_base64")
    @classmethod
    def valid_png(cls, value: str) -> str:
        return bounded_png(value)


def bounded_png(value: str) -> str:
    try:
        image = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("Invalid base64 image") from exc
    if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 256 * 1024:
        raise ValueError("Only a bounded PNG image is allowed")
    return value


class DeliveryResult(BaseModel):
    status: str
    message_id: int | None = None
    retry_after: int | None = None
    reason: str | None = None


class ReactionRequest(BaseModel):
    role: BotRole
    chat_id: int = Field(gt=0)
    message_id: int = Field(gt=0)
    emoji: ReactionEmoji


class TypingRequest(BaseModel):
    role: BotRole
    chat_id: int = Field(gt=0)
