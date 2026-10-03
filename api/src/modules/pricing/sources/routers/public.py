from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse
from papilio.api.responses.meta import BaseMeta, PagerMeta

from src.config.security import owner_auth, service_auth
from src.modules.pricing.sources.config.dependencies import (
    SourceID,
    SourceIDPath,
)
from src.modules.pricing.sources.domain.dtos import SourceSearch
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.sources.interfaces import (
    ISearchSources,
    ISourcePriceService,
    ISourceService,
)
from src.modules.pricing.sources.routers.schemas import (
    SourceOut,
    SourcePriceOut,
)
from src.modules.pricing.symbols.config.dependencies import SymbolIDPath
from src.modules.pricing.symbols.domain.models import SymbolsMetaModel
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import ChartOutputModel
from src.modules.pricing.ticker.interfaces import (
    ISourcePriceTickerService,
)

router = APIRouter(
    prefix="/internal/pricing/sources",
    tags=["Sources"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

SourceResponse = APIResponse[SourceOut, None]
PagedSourceResponse = APIResponse[SourceOut, BaseMeta]
SourcePricesResponse = APIResponse[SourcePriceOut, SymbolsMetaModel]
SourceChartResponse = APIResponse[ChartOutputModel, SourcesMetaModel]


@router.get(
    "", response_model=SourceResponse, response_model_exclude_none=True
)
async def get_sources(
    service: FromDishka[ISourceService],
) -> SourceResponse:
    """
    List the sources a price can be read from.
    """
    sources = await service.get_all()
    return APIResponse.from_data(SourceOut.from_objs(sources))


@router.get(
    "/search",
    response_model=PagedSourceResponse,
)
async def search_sources(
    data: Annotated[SourceSearch, Query()],
    service: FromDishka[ISearchSources],
) -> PagedSourceResponse:
    """
    Page the sources, filtered.

    Rate limited as a public read.
    """
    paged = await service.execute(data)
    return APIResponse(
        success=True,
        data=SourceOut.from_objs(paged.items),
        meta=BaseMeta(
            pager=PagerMeta.from_total(
                data.page, data.per_page, paged.total_items
            )
        ),
    )


@router.get(
    "/{id:int}",
    response_model=SourceResponse,
)
async def get_source(
    id: SourceID,
    service: FromDishka[ISourceService],
) -> SourceResponse:
    """
    Read one source.
    """
    source = await service.get_by_id(id)
    return APIResponse.from_data(SourceOut.from_obj(source))


@router.get(
    "/{id:int}/prices",
    response_model=SourcePricesResponse,
)
async def get_source_symbol_prices(
    id: SourceID,
    service: FromDishka[ISourcePriceService],
) -> SourcePricesResponse:
    """
    Read what one source last quoted, a row per symbol.
    """
    result = await service.get_by_source_id(id)
    return APIResponse(
        success=True,
        data=SourcePriceOut.from_objs(result.data),
        meta=result.meta,
    )


@router.get(
    "/{source_id:int}/symbols/{symbol_id:int}/chart",
    response_model=SourceChartResponse,
)
async def get_source_symbol_chart(
    source_id: SourceIDPath,
    symbol_id: SymbolIDPath,
    type: ChartType,
    service: FromDishka[ISourcePriceTickerService],
) -> SourceChartResponse:
    """
    Draw one source's series for one symbol over the window the chart type
    names.
    """
    result = await service.get_source_chart_by_symbol(
        source_id, symbol_id, type
    )
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )
