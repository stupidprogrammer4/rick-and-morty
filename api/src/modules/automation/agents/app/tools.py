from datetime import timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.content import DraftCreate, DraftOut
from portal_contracts.enums import BotRole, Category
from portal_contracts.presentation import PortalPresentation
from portal_contracts.telegram import ReactionEmoji, ReactionRequest
from src.modules.automation.agents.app.context import ToolContext
from src.modules.automation.agents.domain.dtos import AuthorizedMission
from src.modules.automation.missions.infra.mysql import MissionRepository
from src.modules.content.drafts.domain.models import DraftEvidenceModel
from src.modules.content.drafts.infra.mysql import DraftEvidenceRepository
from src.modules.content.drafts.interfaces import IDraftService
from src.modules.content.news.domain.dtos import (
    ArticleEvidence,
    CollectNews,
    NewsDraft,
)
from src.modules.content.news.interfaces import IArticleService
from src.modules.content.publications.interfaces import ITelegramGateway
from src.modules.pricing.reports.interfaces import IMarketQuery
from src.shared.dates import as_utc, utc_now
from src.shared.errors import conflict, missing


class AgentToolCommands:
    def __init__(
        self,
        context: ToolContext,
        missions: MissionRepository,
        articles: IArticleService,
        market: IMarketQuery,
        drafts: IDraftService,
        links: DraftEvidenceRepository,
        gateway: ITelegramGateway,
        presentation: PortalPresentation,
    ):
        self.context = context
        self.missions = missions
        self.articles = articles
        self.market = market
        self.drafts = drafts
        self.links = links
        self.gateway = gateway
        self.presentation = presentation

    async def authorize(self) -> AuthorizedMission:
        mission = await self.missions.get(self.context.mission_id)
        if mission is None or mission.owner_id != self.context.owner_id:
            raise missing("mission", self.context.mission_id)
        if (
            mission.status != "running"
            or as_utc(mission.deadline) <= utc_now()
        ):
            raise conflict("مأموریت دیگر فعال نیست.")
        return AuthorizedMission.model_validate(mission, from_attributes=True)

    async def collect_news(self, topic: str) -> list[ArticleEvidence]:
        await self.authorize()
        result = await self.articles.collect(
            self.context.mission_id,
            CollectNews(
                topic=topic,
                since=utc_now() - timedelta(hours=24),
                limit=3,
            ),
        )
        return result

    async def search_news(self) -> list[ArticleEvidence]:
        await self.authorize()
        result = await self.articles.list(self.context.mission_id)
        return result

    async def read_article(self, article_id: int) -> ArticleEvidence:
        await self.authorize()
        result = await self.articles.read(self.context.mission_id, article_id)
        return result

    async def get_market_prices(self) -> str:
        await self.authorize()
        result = await self.market.report()
        return result

    async def react_to_message(self, emoji: ReactionEmoji) -> str:
        mission = await self.authorize()
        if mission.automation_key is not None:
            raise conflict(
                "Scheduled missions have no private message to react to"
            )
        await self.gateway.react(
            ReactionRequest(
                role=BotRole(mission.origin_bot),
                chat_id=mission.origin_chat_id,
                message_id=mission.origin_message_id,
                emoji=emoji,
            )
        )
        return "واکنش ثبت شد."

    async def create_post_draft(self, draft: NewsDraft) -> DraftOut:
        mission = await self.authorize()
        evidence = await self.articles.list(mission.id)
        by_id = {article.id: article for article in evidence}
        used = {id for item in draft.items for id in item.evidence_ids}
        if not used.issubset(by_id) or not used:
            raise ValueError("Draft contains evidence outside this mission")
        lines: list[str] = []
        style = self.presentation
        for index, item in enumerate(draft.items):
            emoji = style.item_emojis[index % len(style.item_emojis)]
            lines.append(
                f"{emoji} {item.title}\n{style.summary_label} {item.summary}"
            )
            lines.extend(
                f"{style.source_label}: {by_id[id].url}"
                for id in item.evidence_ids
            )
        if draft.editorial_note:
            lines.append(style.editorial_label + ": " + draft.editorial_note)
        async with transaction():
            current = await self.missions.get(mission.id, lock=True)
            if (
                current is None
                or current.status != "running"
                or as_utc(current.deadline) <= utc_now()
            ):
                raise conflict("مأموریت لغو یا منقضی شده.")
            result = await self.drafts.create(
                mission.owner_id,
                BotRole(mission.origin_bot),
                DraftCreate(
                    category=Category.NEWS,
                    title=draft.title,
                    text="\n\n".join(lines),
                    publisher_bot=style.posts[Category.NEWS].publisher_bot,
                ),
                key=f"mission:{mission.id}:news",
                mission_id=mission.id,
            )
            await self.links.link_many(
                [
                    DraftEvidenceModel(draft_id=result.id, article_id=id)
                    for id in sorted(used)
                ]
            )
        return result
