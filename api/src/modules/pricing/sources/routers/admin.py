from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse
from papilio.api.responses.meta import BaseMeta, PagerMeta, SortMeta
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.engine.interfaces import ICacheReaderService
from src.modules.pricing.sources.config.constants import SourceIDInput
from src.modules.pricing.sources.config.dependencies import (
    SourceID,
    SourceIDPath,
)
from src.modules.pricing.sources.domain.dtos import (
    SourceConfigUpdate,
    SourceCreate,
    SourceSearch,
    SourceUpdate,
)
from src.modules.pricing.sources.domain.enums import (
    SourceSortBy,
    SourceSwitch,
)
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.sources.interfaces import (
    ICreateSource,
    IGetSourcesWithConfig,
    ISearchSources,
    ISourceConfigService,
    ISourcePriceService,
    ISourceService,
)
from src.modules.pricing.sources.routers.schemas import (
    AdminSourcePriceOut,
    AssetBubblesOut,
    RemovedSourceErrorOut,
    SourceBubbleOut,
    SourceConfigOut,
    SourceOut,
    SourceWithConfigOut,
    SymbolPricesOut,
)
from src.modules.pricing.symbols.config.dependencies import SymbolIDPath
from src.modules.pricing.symbols.domain.models import SymbolsMetaModel
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import ChartOutputModel
from src.modules.pricing.ticker.interfaces import (
    ISourcePriceTickerService,
)

router = APIRouter(
    prefix="/internal/pricing/panel/sources",
    tags=["Panel Sources"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

SourceResponse = APIResponse[SourceOut, None]
PagedSourceResponse = APIResponse[SourceOut, BaseMeta]
SourceWithConfigResponse = APIResponse[SourceWithConfigOut, None]
SourceConfigResponse = APIResponse[SourceConfigOut, None]
SymbolPricesResponse = APIResponse[SymbolPricesOut, None]
AssetBubblesResponse = APIResponse[AssetBubblesOut, None]
SourcePricesResponse = APIResponse[AdminSourcePriceOut, SymbolsMetaModel]
SourceChartResponse = APIResponse[ChartOutputModel, SourcesMetaModel]

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.post(
    "", response_model=SourceResponse, response_model_exclude_none=True
)
async def create_source(
    data: SourceCreate,
    service: FromDishka[ICreateSource],
) -> SourceResponse:
    """
    Add a price source.

    The code is unique across sources; a repeat answers 409.
    A default config row is written alongside it.
    """
    source = await service.execute(data)
    return APIResponse.from_data(SourceOut.from_obj(source))


@router.get(
    "", response_model=SourceResponse, response_model_exclude_none=True
)
async def get_sources(
    service: FromDishka[ISourceService],
) -> SourceResponse:
    """
    List every source, oldest first.
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

    The query matches title and code, and a numeric one also matches the public
    id.
    Markets, how a source is read, whether it is switched on, and whether it is
    failing all narrow the page.
    """
    paged = await service.execute(data)
    return APIResponse(
        success=True,
        data=SourceOut.from_objs(paged.items),
        meta=BaseMeta(
            pager=PagerMeta.from_total(
                data.page, data.per_page, paged.total_items
            ),
            sorts=SortMeta.of(SourceSortBy),
        ),
    )


@router.get(
    "/configs",
    response_model=SourceWithConfigResponse,
)
async def get_sources_with_config(
    service: FromDishka[IGetSourcesWithConfig],
    switch: SourceSwitch | None = None,
) -> SourceWithConfigResponse:
    """
    List every source with its crawl config attached.
    """
    sources = await service.execute(switch)
    return APIResponse.from_data(SourceWithConfigOut.from_objs(sources))


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


@router.patch(
    "/{id:int}",
    response_model=SourceResponse,
)
async def update_source(
    id: SourceID,
    data: SourceUpdate,
    service: FromDishka[ISourceService],
) -> SourceResponse:
    """
    Change a source.

    Only the fields sent are written; an empty body answers 400.
    Switching `is_active` off leaves a source in place but out of every crawl.
    """
    source = await service.update(id, data)
    return APIResponse.from_data(SourceOut.from_obj(source))


@router.delete(
    "/{id:int}",
    response_model=SourceResponse,
)
async def remove_source(
    id: SourceID,
    service: FromDishka[ISourceService],
) -> SourceResponse:
    """
    Delete a source, its config and its prices with it.
    """
    source = await service.remove(id)
    return APIResponse.from_data(SourceOut.from_obj(source))


@router.delete(
    "/{id:int}/error",
    response_model=APIResponse[RemovedSourceErrorOut, None],
)
async def clear_source_error(
    id: SourceID,
    service: FromDishka[ISourceService],
) -> APIResponse[RemovedSourceErrorOut, None]:
    """
    Forget the last error a source reported, so it is no longer shown as
    failing.
    """
    source = await service.clear_error(id)
    return APIResponse.from_data(RemovedSourceErrorOut.from_obj(source))


@router.get(
    "/{id:int}/config",
    response_model=SourceConfigResponse,
)
async def get_source_config(
    id: SourceID,
    service: FromDishka[ISourceConfigService],
) -> SourceConfigResponse:
    """
    Read a source's crawl config — its timeout and the credentials it is called
    with.
    """
    config = await service.get_by_source_id(id)
    return APIResponse.from_data(SourceConfigOut.from_obj(config))


@router.patch(
    "/{id:int}/config",
    response_model=SourceConfigResponse,
)
async def update_source_config(
    id: SourceID,
    data: SourceConfigUpdate,
    service: FromDishka[ISourceConfigService],
) -> SourceConfigResponse:
    """
    Change a source's crawl config.

    Only the fields sent are written; an empty body answers 400.
    """
    config = await service.update(id, data)
    return APIResponse.from_data(SourceConfigOut.from_obj(config))


@router.get(
    "/prices",
    response_model=SymbolPricesResponse,
)
async def get_source_prices(
    service: FromDishka[ICacheReaderService],
) -> SymbolPricesResponse:
    """
    Read what every source last quoted, grouped by the symbol it quoted on.

    Straight from the cache the crawl writes, so it is as fresh as the last
    run.
    """
    readings = await service.get_all()
    board = [
        SymbolPricesOut(
            symbol=symbol, prices=AdminSourcePriceOut.from_objs(rows)
        )
        for symbol, rows in readings.items()
    ]
    return APIResponse.from_data(board)


@router.get(
    "/bubbles",
    response_model=AssetBubblesResponse,
)
async def get_source_bubbles(
    service: FromDishka[ICacheReaderService],
) -> AssetBubblesResponse:
    """
    Read the premium every source last published, grouped by asset.
    """
    readings = await service.get_all_bubbles()
    board = [
        AssetBubblesOut(asset=asset, bubbles=SourceBubbleOut.from_objs(rows))
        for asset, rows in readings.items()
    ]
    return APIResponse.from_data(board)


@router.get(
    "/{id:int}/prices",
    response_model=SourcePricesResponse,
)
async def get_source_symbol_prices(
    id: SourceID,
    service: FromDishka[ISourcePriceService],
) -> SourcePricesResponse:
    """
    Read what one source last quoted, a row per symbol, with the symbols named
    in the meta.
    """
    result = await service.get_by_source_id(id)
    return APIResponse(
        success=True,
        data=AdminSourcePriceOut.from_objs(result.data),
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


@router.get(
    "/batch",
    response_model=SourceResponse,
)
async def get_sources_batch(
    ids: Annotated[list[SourceIDInput], Query(default_factory=list)],
    service: FromDishka[ISourceService],
) -> SourceResponse:
    """
    Read many sources by id, in one request.

    An id nothing answers to is not an error for the whole call: what was
    found comes back as data, and the rest as errors beside it.
    """
    batch = await service.get_batch(ids)
    return APIResponse.from_data(
        SourceOut.from_objs(batch.items), errors=batch.errors
    )
