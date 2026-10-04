import json
from decimal import Decimal
from zoneinfo import ZoneInfo

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.enums import BotRole
from portal_contracts.presentation import PortalPresentation
from src.modules.missions.domain.models import MissionModel
from src.modules.news.interfaces import IArticleService
from src.modules.rick.app.context import ToolContext
from src.modules.rick.domain.dtos import (
    AgentHistory,
    AgentMessage,
    AgentOutcome,
)
from src.modules.rick.domain.models import AgentCheckpointModel, LLMRunModel
from src.modules.rick.infra.mcp import MissionMCPClient
from src.modules.rick.infra.mysql import (
    AIBudgetRepository,
    CheckpointRepository,
    LLMRunRepository,
)
from src.modules.rick.interfaces import ILLMClient
from src.shared.dates import as_utc, utc_now


class MissionAgentCommands:
    def __init__(
        self,
        checkpoints: CheckpointRepository,
        budgets: AIBudgetRepository,
        runs: LLMRunRepository,
        llm: ILLMClient,
        settings: PortalConfiguration,
        mcp: MissionMCPClient,
        presentation: PortalPresentation,
        articles: IArticleService,
    ):
        self.checkpoints = checkpoints
        self.budgets = budgets
        self.runs = runs
        self.llm = llm
        self.settings = settings
        self.mcp = mcp
        self.presentation = presentation
        self.articles = articles

    async def step(
        self, mission: MissionModel, *, tools_enabled: bool = True
    ) -> AgentOutcome:
        ai = self.settings.ai
        if ai.mode == "disabled":
            raise ValueError(
                "OpenRouter هنوز فعال نشده؛ مدل و نرخ هزینه را تنظیم کن."
            )
        if ai.mode == "fake":
            return AgentOutcome(text="[آزمایشی] خب پویا، مسیر ریک اجرا شد.")
        if (
            ai.input_usd_per_million is None
            or ai.output_usd_per_million is None
        ):
            raise ValueError("نرخ هزینه مدل برای کنترل بودجه تنظیم نشده.")
        checkpoint = await self.checkpoints.get(mission.id)
        if checkpoint is None:
            role = "morty" if mission.actor == "morty" else "rick"
            system = self.presentation.voices[BotRole(role)].system_prompt
            history = AgentHistory(
                messages=[
                    AgentMessage(role="system", content=system),
                    AgentMessage(role="user", content=mission.text),
                ]
            )
            if mission.automation_key is not None and mission.intent == "news":
                evidence = await self.articles.list(mission.id)
                history.messages.append(
                    AgentMessage(
                        role="user",
                        content=json.dumps(
                            {
                                "untrusted_article_evidence": [
                                    item.model_dump(mode="json")
                                    for item in evidence
                                ]
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
            checkpoint = AgentCheckpointModel(
                mission_id=mission.id, history=history.model_dump_json()
            )
        else:
            history = AgentHistory.model_validate_json(checkpoint.history)
        if checkpoint.requests >= ai.max_requests:
            raise ValueError("سقف درخواست مدل تمام شد.")
        context = ToolContext(owner_id=mission.owner_id, mission_id=mission.id)
        async with self.mcp.connect(context) as session:
            discovered = await self.mcp.tools(session)
            tools = discovered if tools_enabled else []
            if mission.automation_key is not None:
                tools = [
                    tool
                    for tool in tools
                    if tool["function"]["name"] == "create_post_draft"
                ]
            # UTF-8 bytes bound token count conservatively for Persian text.
            estimated = len(history.model_dump_json().encode()) + len(
                json.dumps(tools).encode()
            )
            if checkpoint.input_tokens + estimated > ai.max_input_tokens:
                raise ValueError("سقف ورودی مدل تمام شد.")
            maximum = (
                Decimal(estimated) * Decimal(ai.input_usd_per_million)
                + Decimal(ai.max_output_tokens)
                * Decimal(ai.output_usd_per_million)
            ) / Decimal(1_000_000) + ai.maximum_request_usd
            day = (
                utc_now()
                .astimezone(ZoneInfo(self.settings.portal.timezone))
                .date()
            )
            async with transaction():
                budget = await self.budgets.lock(day)
                if budget.reserved_usd + maximum > Decimal(
                    ai.daily_budget_usd
                ):
                    raise ValueError("بودجه روزانه مدل تمام شد.")
                await self.budgets.adjust(day, maximum)
                checkpoint.requests += 1
                await self.checkpoints.save(checkpoint)
                run = await self.runs.create(
                    LLMRunModel(
                        mission_id=mission.id,
                        request_no=checkpoint.requests,
                        budget_day=day,
                        reserved_usd=maximum,
                        status="sending",
                    )
                )
            try:
                reply = await self.llm.complete(history, tools)
            except Exception:
                async with transaction():
                    run.status = "unknown"
                    await self.runs.save(run)
                raise
            async with transaction():
                run.status = "completed"
                run.input_tokens = reply.input_tokens
                run.output_tokens = reply.output_tokens
                if reply.cost_usd is not None:
                    actual = Decimal(reply.cost_usd)
                    if actual.is_finite() and actual >= 0:
                        run.actual_usd = actual
                        await self.budgets.lock(day)
                        await self.budgets.adjust(day, actual - maximum)
                await self.runs.save(run)
            if as_utc(mission.deadline) <= utc_now():
                raise ValueError("مهلت مأموریت تمام شد.")
            history.messages.append(reply.message)
            checkpoint.input_tokens += reply.input_tokens
            calls = reply.message.tool_calls or []
            if len(calls) > 1:
                history.messages.extend(
                    AgentMessage(
                        role="tool",
                        tool_call_id=call.id,
                        content=(
                            "No tools were executed. Send only one tool call "
                            "per response. For news, combine at most two "
                            "articles into one create_post_draft call."
                        ),
                    )
                    for call in calls
                )
                checkpoint.history = history.model_dump_json()
                async with transaction():
                    await self.checkpoints.save(checkpoint)
                return AgentOutcome(waiting=True)
            if calls:
                call = calls[0]
                allowed = {tool["function"]["name"] for tool in tools}
                if call.function.name not in allowed:
                    raise ValueError("Unknown tool")
                if checkpoint.tools >= ai.max_tools:
                    raise ValueError("سقف ابزارهای مأموریت تمام شد.")
                if call.function.name == "react_to_message":
                    if checkpoint.reactions >= ai.max_reactions:
                        raise ValueError("Reaction limit reached")
                    checkpoint.reactions += 1
                checkpoint.tools += 1
                async with transaction():
                    await self.checkpoints.save(checkpoint)
                content = await self.mcp.execute(
                    session, call.function.name, call.function.arguments
                )
                history.messages.append(
                    AgentMessage(
                        role="tool", content=content, tool_call_id=call.id
                    )
                )
                checkpoint.history = history.model_dump_json()
                async with transaction():
                    await self.checkpoints.save(checkpoint)
                if call.function.name == "create_post_draft":
                    data = json.loads(content)
                    return AgentOutcome(
                        text=self.presentation.voices[
                            BotRole(mission.origin_bot)
                        ].draft_ready,
                        draft_id=data["id"],
                        revision=data["revision"],
                    )
                return AgentOutcome(waiting=True)
            if mission.intent in {"news", "summary"}:
                raise ValueError(
                    "مدل پیش‌نویس مستند نساخت؛ متن آزاد منتشر نمی‌شود."
                )
            return AgentOutcome(text=reply.message.content or "پاسخ خالی مدل.")
