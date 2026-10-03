from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.config.dependencies import AssetIDPath
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.symbols.config.dependencies import SymbolID
from src.modules.pricing.symbols.interfaces import ISymbolService
from src.modules.pricing.symbols.routers.schemas import SymbolOut
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import SourceChartOutputModel
from src.modules.pricing.ticker.interfaces import (
    ISourcePriceTickerService,
)

router = APIRouter(
    prefix="/internal/pricing/symbols",
    tags=["Symbols"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

SymbolResponse = APIResponse[SymbolOut, None]
SymbolChartResponse = APIResponse[SourceChartOutputModel, SourcesMetaModel]


@router.get(
    "", response_model=SymbolResponse, response_model_exclude_none=True
)
async def get_symbols(
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    List the symbols prices are quoted on.
    """
    symbols = await service.get_all()
    return APIResponse.from_data(SymbolOut.from_objs(symbols))


@router.get(
    "/assets/{asset_id:int}",
    response_model=SymbolResponse,
)
async def get_asset_symbols(
    asset_id: AssetIDPath,
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    List the symbols one asset is quoted on.
    """
    symbols = await service.get_by_asset_id(asset_id)
    return APIResponse.from_data(SymbolOut.from_objs(symbols))


@router.get(
    "/{id:int}",
    response_model=SymbolResponse,
)
async def get_symbol(
    id: SymbolID,
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    Read one symbol.
    """
    symbol = await service.get_by_id(id)
    return APIResponse.from_data(SymbolOut.from_obj(symbol))


@router.get(
    "/{id:int}/chart",
    response_model=SymbolChartResponse,
)
async def get_symbol_chart(
    id: SymbolID,
    type: ChartType,
    service: FromDishka[ISourcePriceTickerService],
) -> SymbolChartResponse:
    """
    Draw a symbol's series over the window the chart type names.
    """
    result = await service.get_chart_by_symbol(id, type)
    return APIResponse(success=True, data=result.data, meta=result.meta)
