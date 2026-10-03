from enum import StrEnum

from pydantic import BaseModel, Field

from portal_contracts.enums import BotRole


class ReactionEmoji(StrEnum):
    SEEN = "👀"
    THINKING = "🤔"
    AWESOME = "🔥"
    SURPRISED = "🤯"
    LIKE = "👍"
    SAD = "😢"
    CODE = "👨‍💻"


class TelegramDelivery(BaseModel):
    role: BotRole
    chat_id: int
    text: str = Field(min_length=1, max_length=4096)
    publication_id: int | None = None
    draft_id: int | None = None
    revision: int | None = None


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
