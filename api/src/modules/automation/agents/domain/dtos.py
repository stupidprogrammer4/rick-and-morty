from typing import Literal

from pydantic import BaseModel, Field

from portal_contracts.enums import BotRole


class ToolFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


class AgentMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class AgentHistory(BaseModel):
    messages: list[AgentMessage] = Field(default_factory=list)


class LLMReply(BaseModel):
    message: AgentMessage
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: str | None = None


class AuthorizedMission(BaseModel):
    id: int
    owner_id: int
    origin_bot: BotRole
    origin_chat_id: int
    origin_message_id: int
    automation_key: str | None = None
