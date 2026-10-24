import base64

from portal_contracts.enums import BotRole
from portal_contracts.telegram import PublishedChartPage
from src.modules.content.publications.app.charts import gallery_navigation
from src.modules.content.publications.infra.charts import (
    PublicationChartReader,
    PublicationChartRepository,
)
from src.modules.pricing.charts.domain.models import ChartGallery
from src.modules.pricing.charts.interfaces import IAssetChartRenderer
from src.shared.errors import missing


class PublishedChartPageQuery:
    def __init__(
        self,
        repo: PublicationChartRepository,
        reader: PublicationChartReader,
        renderer: IAssetChartRenderer,
    ):
        self.repo, self.reader, self.renderer = repo, reader, renderer

    async def get(
        self,
        chart_id: int,
        page: int,
        role: BotRole,
        chat_id: int,
        message_id: int,
    ) -> PublishedChartPage:
        row = await self.repo.get(chart_id)
        if (
            row is None
            or row.status != "sent"
            or row.gallery_key != "charts"
            or row.message_id != message_id
        ):
            raise missing("published chart", chart_id)
        parent = await self.reader.parent(row.publication_id)
        if (
            parent is None
            or parent.status != "sent"
            or parent.bot_role != role
            or parent.channel_id != chat_id
        ):
            raise missing("published chart", chart_id)
        gallery = ChartGallery.model_validate_json(row.payload)
        if not 0 <= page < len(gallery.cards):
            raise missing("chart page", page)
        card = gallery.cards[page]
        image = await self.renderer.render(card)
        return PublishedChartPage(
            caption=card.caption,
            png_base64=base64.b64encode(image).decode("ascii"),
            navigation=gallery_navigation(
                parent.id, chart_id, page, len(gallery.cards), gallery
            ),
        )
