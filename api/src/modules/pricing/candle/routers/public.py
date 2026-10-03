from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.config.dependencies import AssetID
from src.modules.pricing.assets.domain.models import AssetsMetaModel
from src.modules.pricing.candle.domain.dtos import ParamDTO, SourceParamDTO
from src.modules.pricing.candle.interfaces import (
    ICandleService,
    ISourceCandleService,
)
from src.modules.pricing.candle.routers.schemas import CandleChartOut
from src.modules.pricing.sources.config.dependencies import SourceID
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import ChartOutputModel
from src.modules.pricing.ticker.interfaces import IPriceTickerService

router = APIRouter(
    prefix="/internal/pricing/charts",
    tags=["Charts"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

CandleChartResponse = APIResponse[CandleChartOut, AssetsMetaModel]
SourceCandleChartResponse = APIResponse[CandleChartOut, SourcesMetaModel]
TickerResponse = APIResponse[ChartOutputModel, AssetsMetaModel]


@router.get(
    "/assets/{id:int}/candles",
    response_model=CandleChartResponse,
)
async def get_asset_candles(
    id: AssetID,
    param: Annotated[ParamDTO, Query()],
    service: FromDishka[ICandleService],
) -> CandleChartResponse:
    """
    Read an asset's candles for one time frame.
    """
    result = await service.get_candle(id, param)
    return APIResponse(
        success=True,
        data=CandleChartOut.from_obj(result.data),
        meta=result.meta,
    )


@router.get(
    "/assets/{id:int}/ticker",
    response_model=TickerResponse,
)
async def get_asset_ticker(
    id: AssetID,
    service: FromDishka[IPriceTickerService],
    type: ChartType = ChartType.DAILY,
) -> TickerResponse:
    """
    Read an asset's last price and what it has done since the window opened.
    """
    result = await service.get_chart(id, type)
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )


@router.get(
    "/sources/{id:int}/candles",
    response_model=SourceCandleChartResponse,
)
async def get_source_candles(
    id: SourceID,
    param: Annotated[SourceParamDTO, Query()],
    service: FromDishka[ISourceCandleService],
) -> SourceCandleChartResponse:
    """
    Read one source's candles for a symbol, in one time frame.
    """
    result = await service.get_candle(id, param)
    return APIResponse(
        success=True,
        data=CandleChartOut.from_obj(result.data),
        meta=result.meta,
    )
