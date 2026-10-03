from string import Formatter
from typing import Self

from pydantic import BaseModel, Field, model_validator

from portal_contracts.enums import BotRole, Category
from portal_contracts.telegram import ReactionEmoji


class VoiceProfile(BaseModel):
    system_prompt: str = Field(min_length=100, max_length=16000)
    accepted: str = Field(max_length=600)
    welcome: str = Field(max_length=3000)
    error: str = Field(max_length=1000)
    failed: str = Field(max_length=1000)
    draft_ready: str = Field(max_length=1000)

    @model_validator(mode="after")
    def placeholders_are_known(self) -> Self:
        allowed = {
            "accepted": {"id"},
            "error": {"detail"},
            "failed": {"detail"},
        }
        for field in ("accepted", "welcome", "error", "failed", "draft_ready"):
            for _, name, specification, conversion in Formatter().parse(
                getattr(self, field)
            ):
                if name is not None and (
                    name not in allowed.get(field, set())
                    or specification
                    or conversion
                ):
                    raise ValueError("Unknown voice placeholder")
        return self


class PostStyle(BaseModel):
    publisher_bot: BotRole
    heading: str = Field(max_length=300)
    separator: str = Field(max_length=120)
    footer: str = Field(max_length=300)
    hashtags: str = Field(max_length=300)


class InteractionStyle(BaseModel):
    accepted: ReactionEmoji
    thinking: ReactionEmoji
    success: ReactionEmoji
    failure: ReactionEmoji


class PresentationSettings(BaseModel):
    interactions: InteractionStyle
    item_emojis: list[str] = Field(min_length=1)
    summary_label: str
    source_label: str
    editorial_label: str
    market_heading: str
    quote_time_label: str
    maximum_post_characters: int = Field(ge=200, le=4000)


class PortalPresentation(PresentationSettings):
    voices: dict[BotRole, VoiceProfile]
    posts: dict[Category, PostStyle]
