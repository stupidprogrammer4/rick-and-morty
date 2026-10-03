from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.config.dependencies import AssetIDPath
from src.modules.pricing.engine.interfaces import IAggregatorService
from src.modules.pricing.engine.routers.schemas import (
    AggValueOut,
    SymbolAggMeta,
)
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.sources.routers.schemas import (
    SourceWithPriceOut,
)
from src.modules.pricing.symbols.config.constants import SymbolIDInput
from src.modules.pricing.symbols.config.dependencies import SymbolID
from src.modules.pricing.symbols.domain.dtos import SymbolCreate, SymbolUpdate
from src.modules.pricing.symbols.domain.enums import (
    SymbolCode,
)
from src.modules.pricing.symbols.interfaces import ISymbolService
from src.modules.pricing.symbols.routers.schemas import SymbolOut
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import SourceChartOutputModel
from src.modules.pricing.ticker.interfaces import (
    ISourcePriceTickerService,
)

router = APIRouter(
    prefix="/internal/pricing/panel/symbols",
    tags=["Panel Symbols"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

SymbolResponse = APIResponse[SymbolOut, None]
SymbolChartResponse = APIResponse[SourceChartOutputModel, SourcesMetaModel]
SymbolSourcesResponse = APIResponse[SourceWithPriceOut, SymbolAggMeta]

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.post(
    "", response_model=SymbolResponse, response_model_exclude_none=True
)
async def create_symbol(
    data: SymbolCreate,
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    Add a symbol — one line an asset is quoted on.

    The code is unique across symbols; a repeat answers 409.
    """
    symbol = await service.create(data)
    return APIResponse.from_data(SymbolOut.from_obj(symbol))


@router.get(
    "", response_model=SymbolResponse, response_model_exclude_none=True
)
async def get_symbols(
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    List every symbol, oldest first.
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


@router.patch(
    "/{id:int}",
    response_model=SymbolResponse,
)
async def update_symbol(
    id: SymbolID,
    data: SymbolUpdate,
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    Change a symbol.

    Only the fields sent are written; an empty body answers 400.
    """
    symbol = await service.update(id, data)
    return APIResponse.from_data(SymbolOut.from_obj(symbol))


@router.delete(
    "/{id:int}",
    response_model=SymbolResponse,
)
async def remove_symbol(
    id: SymbolID,
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    Delete a symbol and the prices quoted on it.
    """
    symbol = await service.remove(id)
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
    Draw a symbol's series over the window the chart type names, with the
    sources behind it in the meta.
    """
    result = await service.get_chart_by_symbol(id, type)
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )


@router.get(
    "/{code}/sources",
    response_model=SymbolSourcesResponse,
)
async def get_symbol_sources(
    code: SymbolCode,
    service: FromDishka[IAggregatorService],
) -> SymbolSourcesResponse:
    """
    Read what every source last quoted on one symbol, and how the calculator
    judged each of them.
    """
    result = await service.stats(code)
    return APIResponse(
        success=True,
        data=SourceWithPriceOut.from_objs(result.sources),
        meta=SymbolAggMeta(
            symbol_id=result.symbol_id,
            agg_type=result.agg_type,
            aggs=AggValueOut.from_objs(result.aggs),
        ),
    )


@router.get(
    "/batch",
    response_model=SymbolResponse,
)
async def get_symbols_batch(
    ids: Annotated[list[SymbolIDInput], Query(default_factory=list)],
    service: FromDishka[ISymbolService],
) -> SymbolResponse:
    """
    Read many symbols by id, in one request.

    An id nothing answers to is not an error for the whole call: what was
    found comes back as data, and the rest as errors beside it.
    """
    batch = await service.get_batch(ids)
    return APIResponse.from_data(
        SymbolOut.from_objs(batch.items), errors=batch.errors
    )
