import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.modules.automation.agents.app.context import ToolContext


class MCPToolError(ValueError):
    """A rejected tool call that the model can correct within its budget."""


class MissionMCPClient:
    @asynccontextmanager
    async def connect(
        self, context: ToolContext
    ) -> AsyncIterator[ClientSession]:
        environment = {
            **os.environ,
            "PORTAL_MCP_OWNER": str(context.owner_id),
            "PORTAL_MCP_MISSION": str(context.mission_id),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.apps.mcp"],
            env=environment,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=40
            ) as session:
                await session.initialize()
                yield session

    async def tools(self, session: ClientSession) -> list[dict[str, Any]]:
        result = await session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in result.tools
        ]

    async def execute(
        self, session: ClientSession, name: str, arguments: str
    ) -> str:
        data = json.loads(arguments)
        if not isinstance(data, dict):
            raise ValueError("Tool arguments must be an object")
        result = await session.call_tool(name, data)
        if result.is_error:
            detail = " ".join(
                item.text for item in result.content if item.type == "text"
            )
            raise MCPToolError(detail[:1500] or "MCP tool failed")
        if result.structured_content is not None:
            return json.dumps(result.structured_content, ensure_ascii=False)
        texts = [item.text for item in result.content if item.type == "text"]
        if len(texts) != 1:
            raise ValueError("Unexpected MCP result content")
        return texts[0]
