from collections.abc import Awaitable
from typing import Any, Protocol

from portal_contracts.automation import AgentOutcome, AgentRequest
from portal_contracts.content import DraftOut
from portal_contracts.telegram import ReactionEmoji
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AuthorizedMission,
    LLMReply,
)
from src.modules.content.news.domain.dtos import ArticleEvidence, NewsDraft


class ILLMClient(Protocol):
    def complete(
        self, history: AgentHistory, tools: list[dict[str, Any]]
    ) -> Awaitable[LLMReply]: ...


class IRickAgent(Protocol):
    def step(
        self, mission: AgentRequest, *, tools_enabled: bool = True
    ) -> Awaitable[AgentOutcome]: ...


class IAgentToolCommands(Protocol):
    async def authorize(self) -> AuthorizedMission: ...

    async def collect_news(self, topic: str) -> list[ArticleEvidence]: ...

    async def search_news(self) -> list[ArticleEvidence]: ...

    async def read_article(self, article_id: int) -> ArticleEvidence: ...

    async def get_market_prices(self) -> str: ...

    async def react_to_message(self, emoji: ReactionEmoji) -> str: ...

    async def create_post_draft(self, draft: NewsDraft) -> DraftOut: ...
