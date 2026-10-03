from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.domain.models import AssetsMetaModel
from src.modules.pricing.assets.interfaces import IAssetService
from src.modules.pricing.bubbles.config.dependencies import BubbleID
from src.modules.pricing.bubbles.interfaces import (
    IBubbleService,
    IBubbleSourceService,
)
from src.modules.pricing.bubbles.routers.schemas import BubbleOut
from src.modules.pricing.sources.config.dependencies import SourceIDPath
from src.modules.pricing.sources.domain.models import (
    SourceOnlyMetaModel,
    SourcesMetaModel,
)
from src.modules.pricing.sources.routers.schemas import (
    SourceBubbleOut,
)
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import (
    ChartOutputModel,
    SourceChartOutputModel,
)
from src.modules.pricing.ticker.interfaces import (
    IBubbleTickerService,
    ISourceBubbleTickerService,
)

router = APIRouter(
    prefix="/internal/pricing/bubbles",
    tags=["Bubbles"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

BubbleResponse = APIResponse[BubbleOut, None]
BubbleSourcesResponse = APIResponse[SourceBubbleOut, SourceOnlyMetaModel]
BubbleChartResponse = APIResponse[ChartOutputModel, AssetsMetaModel]
SourceBubbleChartResponse = APIResponse[
    SourceChartOutputModel, SourcesMetaModel
]
SingleSourceBubbleChartResponse = APIResponse[
    ChartOutputModel, SourcesMetaModel
]


@router.get(
    "", response_model=BubbleResponse, response_model_exclude_none=True
)
async def get_bubbles(
    service: FromDishka[IBubbleService],
) -> BubbleResponse:
    """
    List the bubbles the shop settles.
    """
    bubbles = await service.get_all()
    return APIResponse.from_data(BubbleOut.from_objs(bubbles))


@router.get(
    "/{id:int}",
    response_model=BubbleResponse,
)
async def get_bubble(
    id: BubbleID,
    service: FromDishka[IBubbleService],
) -> BubbleResponse:
    """
    Read one bubble.
    """
    bubble = await service.get_by_id(id)
    return APIResponse.from_data(BubbleOut.from_obj(bubble))


@router.get(
    "/{code}/sources",
    response_model=BubbleSourcesResponse,
)
async def get_bubble_sources(
    code: AssetCode,
    service: FromDishka[IBubbleSourceService],
) -> BubbleSourcesResponse:
    """
    Read the premium every source last published for one bubble.
    """
    result = await service.get_by_asset_code(code)
    return APIResponse(
        success=True,
        data=SourceBubbleOut.from_objs(result.data),
        meta=result.meta,
    )


@router.get(
    "/{code}/chart",
    response_model=BubbleChartResponse,
)
async def get_bubble_chart(
    code: AssetCode,
    type: ChartType,
    assets: FromDishka[IAssetService],
    service: FromDishka[IBubbleTickerService],
) -> BubbleChartResponse:
    """
    Draw a bubble's series over the window the chart type names.
    """
    asset = await assets.get_by_code(code)
    result = await service.get_chart(asset.id, type)
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )


@router.get(
    "/{code}/sources/chart",
    response_model=SourceBubbleChartResponse,
)
async def get_bubble_source_charts(
    code: AssetCode,
    type: ChartType,
    assets: FromDishka[IAssetService],
    service: FromDishka[ISourceBubbleTickerService],
) -> SourceBubbleChartResponse:
    """
    Draw the series of every source publishing one bubble, side by side.
    """
    asset = await assets.get_by_code(code)
    result = await service.get_chart_by_asset(asset.id, type)
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )


@router.get(
    "/{code}/sources/{source_id:int}/chart",
    response_model=SingleSourceBubbleChartResponse,
)
async def get_bubble_source_chart(
    code: AssetCode,
    source_id: SourceIDPath,
    type: ChartType,
    assets: FromDishka[IAssetService],
    service: FromDishka[ISourceBubbleTickerService],
) -> SingleSourceBubbleChartResponse:
    """
    Draw one source's series for one bubble.
    """
    asset = await assets.get_by_code(code)
    result = await service.get_source_chart_by_asset(source_id, asset.id, type)
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )
