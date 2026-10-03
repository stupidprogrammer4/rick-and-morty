import asyncio
import re
from datetime import timedelta
from html import escape

from papilio.infra.db.transaction import transaction

from portal_contracts.enums import BotRole
from portal_contracts.presentation import PortalPresentation
from portal_contracts.telegram import (
    ReactionRequest,
    TypingRequest,
)
from src.modules.content.interfaces import IDraftService
from src.modules.market.domain.dtos import MarketSnapshot
from src.modules.market.interfaces import IMarketDraftCommands, IMarketQuery
from src.modules.missions.domain.dtos import MissionChange, MissionClaim
from src.modules.missions.infra.mysql import MissionRepository
from src.modules.news.domain.dtos import CollectNews
from src.modules.news.interfaces import IArticleService
from src.modules.publishing.domain.models import PrivateReplyModel
from src.modules.publishing.interfaces import (
    IPrivateReplyService,
    ITelegramGateway,
)
from src.modules.rick.domain.dtos import AgentOutcome
from src.modules.rick.interfaces import IRickAgent
from src.shared.dates import as_utc, utc_now


class MissionExecutor:
    def __init__(
        self,
        repo: MissionRepository,
        articles: IArticleService,
        market: IMarketQuery,
        market_drafts: IMarketDraftCommands,
        agent: IRickAgent,
        drafts: IDraftService,
        replies: IPrivateReplyService,
        gateway: ITelegramGateway,
        presentation: PortalPresentation,
    ):
        self.repo = repo
        self.articles = articles
        self.market = market
        self.market_drafts = market_drafts
        self.agent = agent
        self.drafts = drafts
        self.replies = replies
        self.gateway = gateway
        self.presentation = presentation

    async def execute(self, mission_id: int) -> None:
        async with transaction():
            mission = await self.repo.get(mission_id, lock=True)
            if mission is None or mission.status != "queued":
                return
            now = utc_now()
            if as_utc(mission.deadline) <= now:
                await self.repo.change(
                    mission_id,
                    MissionChange(
                        status="expired",
                        stage="expired",
                    ),
                )
                return
            claimed = await self.repo.claim(
                mission_id,
                MissionClaim(
                    now=now,
                    lease_expires_at=as_utc(mission.deadline),
                    version=mission.version,
                ),
            )
            if not claimed:
                return
            # Snapshot before closing the short claim transaction.
            mission = mission.model_copy()
        role = BotRole(mission.origin_bot)
        await asyncio.gather(
            self.gateway.typing(
                TypingRequest(role=role, chat_id=mission.origin_chat_id)
            ),
            self.gateway.react(
                ReactionRequest(
                    role=role,
                    chat_id=mission.origin_chat_id,
                    message_id=mission.origin_message_id,
                    emoji=self.presentation.interactions.thinking,
                )
            ),
            return_exceptions=True,
        )
        market_snapshot: MarketSnapshot | None = None
        try:
            remaining = (as_utc(mission.deadline) - utc_now()).total_seconds()
            async with asyncio.timeout(max(0, remaining)):
                if mission.intent == "prices":
                    market_snapshot = await self.market.snapshot()
                    outcome = AgentOutcome()
                elif mission.stage == "accepted" and mission.intent == "news":
                    evidence = await self.articles.collect(
                        mission.id,
                        CollectNews(
                            topic=mission.text[:64],
                            since=utc_now() - timedelta(hours=24),
                        ),
                    )
                    if not evidence:
                        raise ValueError("متن کافی برای خبر پیدا نشد.")
                    outcome = AgentOutcome(waiting=True)
                elif (
                    mission.stage == "accepted" and mission.intent == "summary"
                ):
                    match = re.search(r"https://\S+", mission.text)
                    if match is None:
                        raise ValueError("لینک HTTPS مقاله لازم است.")
                    await self.articles.read_url(mission.id, match.group())
                    outcome = AgentOutcome(waiting=True)
                else:
                    outcome = await self.agent.step(mission)
            failure = None
        except Exception as exc:
            outcome = AgentOutcome()
            # Provider bodies and raw HTTP exception strings can carry secrets.
            failure = (
                str(exc)[:350]
                if isinstance(exc, ValueError)
                else type(exc).__name__
            )
        async with transaction():
            current = await self.repo.get(mission_id, lock=True)
            if current is None or current.status != "running":
                return
            if as_utc(current.deadline) <= utc_now():
                failure = "مهلت مأموریت تمام شد."
            if failure is not None:
                await self.repo.change(
                    mission_id,
                    MissionChange(
                        status="failed",
                        stage="failed",
                        failure_reason=failure,
                    ),
                )
                text = self.presentation.voices[role].failed.format(
                    detail=failure
                )
                await self.replies.create(
                    PrivateReplyModel(
                        mission_id=mission_id,
                        owner_id=mission.owner_id,
                        origin_bot=role,
                        text=escape(text),
                    )
                )
            elif outcome.waiting:
                await self.repo.change(
                    mission_id,
                    MissionChange(
                        status="queued",
                        stage="model",
                    ),
                )
                return
            else:
                if market_snapshot is not None:
                    draft = await self.market_drafts.from_snapshot(
                        current, market_snapshot
                    )
                    outcome = AgentOutcome(
                        text=self.presentation.voices[role].draft_ready,
                        draft_id=draft.id,
                        revision=draft.revision,
                    )
                result_text = outcome.text or "آماده شد."
                if outcome.draft_id is not None:
                    draft = await self.drafts.get(
                        outcome.draft_id, mission.owner_id
                    )
                    result_text += (
                        f"\n\nپیش‌نویس #{draft.id} · نسخه {draft.revision}"
                        f"\n{draft.title}\n\n{draft.text}"
                    )
                await self.repo.change(
                    mission_id,
                    MissionChange(
                        status="draft_ready"
                        if outcome.draft_id
                        else "completed",
                        stage="done",
                        result=result_text,
                    ),
                )
                await self.replies.create(
                    PrivateReplyModel(
                        mission_id=mission_id,
                        owner_id=mission.owner_id,
                        origin_bot=role,
                        text=escape(result_text),
                        draft_id=outcome.draft_id,
                        revision=outcome.revision,
                    )
                )
        await asyncio.gather(
            self.gateway.react(
                ReactionRequest(
                    role=role,
                    chat_id=mission.origin_chat_id,
                    message_id=mission.origin_message_id,
                    emoji=self.presentation.interactions.failure
                    if failure
                    else self.presentation.interactions.success,
                )
            ),
            return_exceptions=True,
        )
