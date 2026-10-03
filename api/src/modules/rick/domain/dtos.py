from typing import Literal

from pydantic import BaseModel, Field


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


class AgentOutcome(BaseModel):
    waiting: bool = False
    text: str | None = None
    draft_id: int | None = None
    revision: int | None = None
