from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import DraftCreate, DraftOut
from portal_contracts.enums import BotRole, Category
from portal_contracts.occasions import OccasionDay, OccasionDraft
from portal_contracts.presentation import PortalPresentation
from portal_contracts.public_text import validate_public_voice
from portal_contracts.telegram import ReactionEmoji, ReactionRequest
from src.modules.automation.agents.app.context import ToolContext
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AuthorizedMission,
)
from src.modules.automation.agents.infra.mysql import CheckpointRepository
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
from src.modules.content.occasions.app.calendar import OccasionCalendar
from src.modules.content.publications.interfaces import ITelegramGateway
from src.modules.pricing.reports.interfaces import IMarketQuery
from src.shared.dates import as_utc, utc_now
from src.shared.errors import conflict, missing


def calendar_evidence(history: AgentHistory) -> OccasionDay | None:
    calls = {
        call.id
        for message in history.messages
        for call in message.tool_calls or []
        if call.function.name == "get_calendar_occasions"
    }
    for message in reversed(history.messages):
        if message.role == "tool" and message.tool_call_id in calls:
            return OccasionDay.model_validate_json(message.content or "")
    return None


def occasion_text(day: OccasionDay, draft: OccasionDraft) -> str:
    ids = [comment.event_id for comment in draft.comments]
    if (
        draft.date != day.date
        or len(ids) != len(set(ids))
        or set(ids) != {event.id for event in day.events}
    ):
        raise ValueError("Include every calendar event exactly once")
    if not day.events:
        raise ValueError("No selected occasions to announce")
    public_fields = [draft.intro, draft.outro] + [
        comment.text for comment in draft.comments
    ]
    validate_public_voice(public_fields)
    comments = {comment.event_id: comment.text for comment in draft.comments}
    lines = [draft.intro]
    lines.extend(
        f"{event.title}\n{comments[event.id]}" for event in day.events
    )
    lines.append(draft.outro)
    return "\n\n".join(line for line in lines if line.strip())


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
        calendar: OccasionCalendar,
        checkpoints: CheckpointRepository,
        settings: PortalConfiguration,
    ):
        self.context = context
        self.missions = missions
        self.articles = articles
        self.market = market
        self.drafts = drafts
        self.links = links
        self.gateway = gateway
        self.presentation = presentation
        self.calendar = calendar
        self.checkpoints = checkpoints
        self.settings = settings

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

    async def get_calendar_occasions(
        self, on_date: str | None = None
    ) -> OccasionDay:
        mission = await self.authorize()
        requested = date.fromisoformat(on_date) if on_date else None
        target = None
        if mission.intent == "occasions":
            if mission.automation_key is not None:
                slot = int(mission.automation_key.split(":", 1)[1])
                target = datetime.fromtimestamp(slot / 1_000_000, UTC)
                target = target.astimezone(
                    ZoneInfo(self.settings.portal.timezone)
                ).date()
            elif mission.text != "today":
                target = date.fromisoformat(mission.text)
            else:
                target = (
                    utc_now()
                    .astimezone(ZoneInfo(self.settings.portal.timezone))
                    .date()
                )
            if requested is not None and requested != target:
                raise ValueError("Use the mission's calendar date")
        return self.calendar.day(target or requested)

    async def create_occasion_draft(self, draft: OccasionDraft) -> DraftOut:
        mission = await self.authorize()
        if mission.intent != "occasions":
            raise conflict("Use an occasions mission to create this draft")
        checkpoint = await self.checkpoints.get(mission.id)
        day = (
            calendar_evidence(
                AgentHistory.model_validate_json(checkpoint.history)
            )
            if checkpoint is not None
            else None
        )
        if day is None:
            raise ValueError("Read get_calendar_occasions before drafting")
        data = DraftCreate(
            category=Category.OCCASIONS,
            title=(f"امروز توی این بُعد · {day.date.isoformat()}"),
            text=occasion_text(day, draft),
            publisher_bot=BotRole.RICK,
        )
        async with transaction():
            current = await self.missions.get(mission.id, lock=True)
            if (
                current is None
                or current.status != "running"
                or as_utc(current.deadline) <= utc_now()
            ):
                raise conflict("مأموریت لغو یا منقضی شده.")
            return await self.drafts.create(
                mission.owner_id,
                BotRole(mission.origin_bot),
                data,
                key=f"mission:{mission.id}:occasions",
                mission_id=mission.id,
            )

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
        spoken = mission.intent == "news"
        if spoken:
            if len(used) > 2:
                raise ValueError("News drafts may use at most two articles")
            validate_public_voice(
                [draft.title, draft.editorial_note or ""]
                + [
                    field
                    for item in draft.items
                    for field in (item.title, item.summary)
                ]
            )
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
            lines.append("نظر: " + draft.editorial_note)
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
