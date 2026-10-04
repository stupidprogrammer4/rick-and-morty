import asyncio
import re
from datetime import timedelta
from html import escape

from papilio.infra.db.transaction import transaction

from portal_contracts.automation import AgentOutcome, AgentRequest
from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import DraftDecision, PublishRequest
from portal_contracts.enums import BotRole
from portal_contracts.presentation import PortalPresentation
from portal_contracts.telegram import (
    ReactionRequest,
    TypingRequest,
)
from src.modules.automation.agents.interfaces import IRickAgent
from src.modules.automation.missions.domain.dtos import (
    MissionChange,
    MissionClaim,
)
from src.modules.automation.missions.domain.models import MissionModel
from src.modules.automation.missions.infra.mysql import MissionRepository
from src.modules.content.drafts.domain.dtos import MarketDraftContext
from src.modules.content.drafts.interfaces import (
    IDraftService,
    IMarketDraftCommands,
)
from src.modules.content.news.domain.dtos import CollectNews
from src.modules.content.news.interfaces import IArticleService
from src.modules.content.publications.interfaces import (
    IPublicationCommands,
    ITelegramGateway,
)
from src.modules.content.replies.domain.models import PrivateReplyModel
from src.modules.content.replies.interfaces import IPrivateReplyService
from src.modules.pricing.reports.domain.dtos import MarketSnapshot
from src.modules.pricing.reports.interfaces import (
    IMarketQuery,
)
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
        settings: PortalConfiguration,
        publications: IPublicationCommands,
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
        self.settings = settings
        self.publications = publications

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
        if mission.automation_key is None:
            await self.interact(mission, role)
        market_snapshot: MarketSnapshot | None = None
        try:
            remaining = (as_utc(mission.deadline) - utc_now()).total_seconds()
            async with asyncio.timeout(max(0, remaining)):
                if mission.intent == "prices":
                    market_snapshot = await self.market.snapshot()
                    outcome = AgentOutcome()
                elif mission.stage == "accepted" and mission.intent == "news":
                    rule = self.settings.automation.news
                    automatic = mission.automation_key is not None
                    evidence = await self.articles.collect(
                        mission.id,
                        CollectNews(
                            topic=rule.topic
                            if automatic
                            else mission.text[:64],
                            since=utc_now()
                            - timedelta(
                                seconds=rule.lookback_seconds
                                if automatic
                                else 86400
                            ),
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
                    outcome = await self.agent.step(
                        AgentRequest.model_validate(
                            mission, from_attributes=True
                        )
                    )
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
                if mission.automation_key is None:
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
                    MissionChange(status="queued", stage="model"),
                )
                return
            else:
                if market_snapshot is not None:
                    draft = await self.market_drafts.from_snapshot(
                        MarketDraftContext.model_validate(
                            current, from_attributes=True
                        ),
                        market_snapshot,
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
                    if mission.automation_key is not None:
                        await self.schedule_draft(
                            current, draft.id, draft.revision
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
                if mission.automation_key is None:
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
        if mission.automation_key is None:
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

    async def schedule_draft(
        self, mission: MissionModel, draft_id: int, revision: int
    ) -> None:
        policy = self.settings.automation
        rule = policy.news if mission.intent == "news" else policy.prices
        if not rule.enabled or policy.owner_id != mission.owner_id:
            return
        role = BotRole(mission.origin_bot)
        await self.drafts.decide(
            draft_id,
            mission.owner_id,
            DraftDecision(revision=revision, origin_bot=role),
            approve=True,
        )
        await self.publications.schedule(
            draft_id,
            mission.owner_id,
            PublishRequest(revision=revision, origin_bot=role),
        )

    async def interact(self, mission: MissionModel, role: BotRole) -> None:
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
