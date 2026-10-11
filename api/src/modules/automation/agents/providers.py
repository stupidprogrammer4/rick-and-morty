import os

from dishka import Provider, Scope, provide

from src.modules.automation.agents.app.agent import MissionAgentCommands
from src.modules.automation.agents.app.context import ToolContext
from src.modules.automation.agents.app.tools import AgentToolCommands
from src.modules.automation.agents.infra.mcp import MissionMCPClient
from src.modules.automation.agents.infra.mysql import (
    AIBudgetRepository,
    CheckpointRepository,
    LLMRunRepository,
)
from src.modules.automation.agents.infra.openrouter import OpenRouterClient
from src.modules.automation.agents.interfaces import (
    IAgentToolCommands,
    ILLMClient,
    IRickAgent,
)


class RickProvider(Provider):
    scope = Scope.REQUEST
    checkpoints = provide(CheckpointRepository)
    budgets = provide(AIBudgetRepository)
    runs = provide(LLMRunRepository)
    llm = provide(OpenRouterClient, provides=ILLMClient)
    agent = provide(MissionAgentCommands, provides=IRickAgent)
    mcp = provide(MissionMCPClient, scope=Scope.APP)
    tools = provide(AgentToolCommands, provides=IAgentToolCommands)

    @provide(scope=Scope.APP)
    def context(self) -> ToolContext:
        return ToolContext(
            owner_id=int(os.getenv("PORTAL_MCP_OWNER", "0")),
            mission_id=int(os.getenv("PORTAL_MCP_MISSION", "0")),
        )
