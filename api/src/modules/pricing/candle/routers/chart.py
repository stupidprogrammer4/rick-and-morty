from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse
from papilio.schemas.outputs import EnumGroupOut

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

router = APIRouter(
    prefix="/internal/pricing/panel/candles",
    tags=["Panel Candles"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

CandleChartResponse = APIResponse[CandleChartOut, AssetsMetaModel]
SourceCandleChartResponse = APIResponse[CandleChartOut, SourcesMetaModel]

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.get(
    "/assets/{id:int}",
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
    "/sources/{id:int}",
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
