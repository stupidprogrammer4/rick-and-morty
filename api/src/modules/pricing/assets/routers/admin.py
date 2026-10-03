from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse
from papilio.core import resources as framework_resources
from papilio.errors.exceptions import NotFoundException
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.config.constants import AssetIDInput
from src.modules.pricing.assets.config.dependencies import (
    AssetID,
    AssetIDPath,
    AssetSwitchIDPath,
)
from src.modules.pricing.assets.domain.dtos import (
    AssetConfigUpdate,
    AssetCreate,
    AssetSwitchBatchCreate,
    AssetSwitchBatchDelete,
    AssetSwitchBatchUpdate,
    AssetSwitchCreate,
    AssetSwitchPriorityUpdate,
    AssetSwitchUpdate,
    AssetUpdate,
)
from src.modules.pricing.assets.domain.enums import (
    AssetCode,
)
from src.modules.pricing.assets.domain.models import AssetsMetaModel
from src.modules.pricing.assets.interfaces import (
    IAssetConfigService,
    IAssetService,
    IAssetSourcePriceService,
    IAssetSwitchService,
    ICreateAsset,
    IGetAssetsWithConfig,
    IUpdateAssetConfig,
)
from src.modules.pricing.assets.routers.schemas import (
    AssetConfigOut,
    AssetOut,
    AssetPriceOut,
    AssetSwitchOut,
    AssetWithConfigOut,
    RepriceOut,
)
from src.modules.pricing.calculator.interfaces import (
    ICacheReaderService,
    ISymbolConverterService,
)
from src.modules.pricing.calculator.tasks.schedulers.price import (
    RepriceAssetTask as reprice,
)
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.sources.routers.schemas import (
    AdminSourcePriceOut,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import ChartOutputModel
from src.modules.pricing.ticker.interfaces import IPriceTickerService

router = APIRouter(
    prefix="/internal/pricing/panel/assets",
    tags=["Panel Assets"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

AssetResponse = APIResponse[AssetOut, None]
AssetWithConfigResponse = APIResponse[AssetWithConfigOut, None]
AssetConfigResponse = APIResponse[AssetConfigOut, None]
AssetSwitchResponse = APIResponse[AssetSwitchOut, None]
AssetPriceResponse = APIResponse[AssetPriceOut, None]
AssetChartResponse = APIResponse[ChartOutputModel, AssetsMetaModel]
AssetSourcePriceResponse = APIResponse[AdminSourcePriceOut, SourcesMetaModel]
RepriceResponse = APIResponse[RepriceOut, None]

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.post(
    "", response_model=AssetResponse, response_model_exclude_none=True
)
async def create_asset(
    data: AssetCreate,
    service: FromDishka[ICreateAsset],
) -> AssetResponse:
    """
    Add an asset — a thing the shop prices.

    The code is unique across assets; a repeat answers 409.
    A default pricing config is written alongside it.
    """
    asset = await service.execute(data)
    return APIResponse.from_data(AssetOut.from_obj(asset))


@router.get("", response_model=AssetResponse, response_model_exclude_none=True)
async def get_assets(
    service: FromDishka[IAssetService],
) -> AssetResponse:
    """
    List every asset, oldest first.
    """
    assets = await service.get_all()
    return APIResponse.from_data(AssetOut.from_objs(assets))


@router.get(
    "/configs",
    response_model=AssetWithConfigResponse,
)
async def get_assets_with_config(
    service: FromDishka[IGetAssetsWithConfig],
) -> AssetWithConfigResponse:
    """
    List every asset with its pricing config attached.
    """
    assets = await service.execute()
    return APIResponse.from_data(AssetWithConfigOut.from_objs(assets))


@router.get(
    "/{id:int}",
    response_model=AssetResponse,
)
async def get_asset(
    id: AssetID,
    service: FromDishka[IAssetService],
) -> AssetResponse:
    """
    Read one asset.
    """
    asset = await service.get_by_id(id)
    return APIResponse.from_data(AssetOut.from_obj(asset))


@router.patch(
    "/{id:int}",
    response_model=AssetResponse,
)
async def update_asset(
    id: AssetID,
    data: AssetUpdate,
    service: FromDishka[IAssetService],
) -> AssetResponse:
    """
    Change an asset.

    Only the fields sent are written; an empty body answers 400.
    """
    asset = await service.update(id, data)
    return APIResponse.from_data(AssetOut.from_obj(asset))


@router.delete(
    "/{id:int}",
    response_model=AssetResponse,
)
async def remove_asset(
    id: AssetID,
    service: FromDishka[IAssetService],
) -> AssetResponse:
    """
    Delete an asset, its symbols and its prices with it.
    """
    asset = await service.remove(id)
    return APIResponse.from_data(AssetOut.from_obj(asset))


@router.get(
    "/{id:int}/config",
    response_model=AssetConfigResponse,
)
async def get_asset_config(
    id: AssetID,
    service: FromDishka[IAssetConfigService],
) -> AssetConfigResponse:
    """
    Read how an asset is priced — the rule its sources are folded by.
    """
    config = await service.get_by_asset_id(id)
    return APIResponse.from_data(AssetConfigOut.from_obj(config))


@router.patch(
    "/{id:int}/config",
    response_model=AssetConfigResponse,
)
async def update_asset_config(
    id: AssetID,
    data: AssetConfigUpdate,
    service: FromDishka[IUpdateAssetConfig],
) -> AssetConfigResponse:
    """
    Change how an asset is priced.

    Only the fields sent are written; an empty body answers 400.
    """
    config = await service.execute(id, data)
    return APIResponse.from_data(AssetConfigOut.from_obj(config))


@router.get(
    "/{asset_id:int}/switches",
    response_model=AssetSwitchResponse,
)
async def get_asset_switches(
    asset_id: AssetIDPath,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    List the markets an asset is priced from, in the order they are tried.
    """
    switches = await service.get_by_asset_id(asset_id)
    return APIResponse.from_data(AssetSwitchOut.from_objs(switches))


@router.post(
    "/{asset_id:int}/switches",
    response_model=AssetSwitchResponse,
)
async def create_asset_switch(
    asset_id: AssetIDPath,
    data: AssetSwitchCreate,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Add a market to an asset's pricing order.
    """
    switch = await service.create(asset_id, data)
    return APIResponse.from_data(AssetSwitchOut.from_obj(switch))


@router.post(
    "/{asset_id:int}/switches/batch",
    response_model=AssetSwitchResponse,
)
async def batch_create_asset_switches(
    asset_id: AssetIDPath,
    data: AssetSwitchBatchCreate,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Add several markets to an asset's pricing order at once.
    """
    switches = await service.batch_create(asset_id, data)
    return APIResponse.from_data(AssetSwitchOut.from_objs(switches))


@router.put(
    "/{asset_id:int}/switches/batch",
    response_model=AssetSwitchResponse,
)
async def batch_update_asset_switches(
    asset_id: AssetIDPath,
    data: AssetSwitchBatchUpdate,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Change several rows of an asset's pricing order at once.
    """
    switches = await service.batch_update(asset_id, data)
    return APIResponse.from_data(AssetSwitchOut.from_objs(switches))


@router.patch(
    "/{asset_id:int}/switches/batch",
    response_model=AssetSwitchResponse,
)
async def set_asset_switches_priority(
    asset_id: AssetIDPath,
    data: AssetSwitchPriorityUpdate,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Reorder the markets an asset is priced from.

    The order sent is the order they are tried in.
    """
    switches = await service.set_priority(asset_id, data)
    return APIResponse.from_data(AssetSwitchOut.from_objs(switches))


@router.delete(
    "/{asset_id:int}/switches/batch",
    response_model=AssetSwitchResponse,
)
async def batch_remove_asset_switches(
    asset_id: AssetIDPath,
    data: AssetSwitchBatchDelete,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Drop several markets from an asset's pricing order at once.
    """
    dropped = await service.batch_remove(asset_id, data)
    return APIResponse.from_data(
        AssetSwitchOut.from_objs(dropped.items), errors=dropped.errors
    )


@router.patch(
    "/{asset_id:int}/switches/{asset_switch_id:int}",
    response_model=AssetSwitchResponse,
)
async def update_asset_switch(
    asset_id: AssetIDPath,
    asset_switch_id: AssetSwitchIDPath,
    data: AssetSwitchUpdate,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Change one row of an asset's pricing order.
    """
    switch = await service.update(asset_id, asset_switch_id, data)
    return APIResponse.from_data(AssetSwitchOut.from_obj(switch))


@router.delete(
    "/{asset_id:int}/switches/{asset_switch_id:int}",
    response_model=AssetSwitchResponse,
)
async def remove_asset_switch(
    asset_id: AssetIDPath,
    asset_switch_id: AssetSwitchIDPath,
    service: FromDishka[IAssetSwitchService],
) -> AssetSwitchResponse:
    """
    Drop one market from an asset's pricing order.
    """
    switch = await service.remove(asset_id, asset_switch_id)
    return APIResponse.from_data(AssetSwitchOut.from_obj(switch))


@router.post(
    "/{asset_code}/reprice",
    response_model=RepriceResponse,
)
async def reprice_asset(asset_code: AssetCode) -> RepriceResponse:
    """
    Ask for an asset to be priced again.

    The work is queued, not done here; the task id comes back so the run can be
    followed.
    """
    job = await reprice.enqueue(asset_code)
    return APIResponse.from_data(RepriceOut(task_id=job.task_id))


@router.get(
    "/price",
    response_model=AssetPriceResponse,
)
async def get_asset_prices(
    service: FromDishka[ICacheReaderService],
) -> AssetPriceResponse:
    """
    Read what every asset last settled at.
    """
    prices = await service.get_all_prices()
    return APIResponse.from_data(AssetPriceOut.from_objs(prices))


@router.get(
    "/{asset_code}/price",
    response_model=AssetPriceResponse,
)
async def get_asset_price(
    asset_code: AssetCode,
    service: FromDishka[ICacheReaderService],
) -> AssetPriceResponse:
    """
    Read what one asset last settled at.

    An asset that has never been priced answers 404.
    """
    price = await service.get_price(asset_code)
    if price is None:
        raise NotFoundException(
            identifier="code",
            identifier_value=asset_code,
            message=f"Cannot find Price by code with value {asset_code}",
            message_code=framework_resources.NOT_FOUND_ERROR,
            entity="Price",
        )
    return APIResponse.from_data(AssetPriceOut.from_obj(price))


@router.get(
    "/{id:int}/sources",
    response_model=AssetSourcePriceResponse,
)
async def get_asset_source_prices(
    id: AssetID,
    service: FromDishka[IAssetSourcePriceService],
) -> AssetSourcePriceResponse:
    """
    Read what every source of one asset last quoted, and how each was judged.
    """
    result = await service.get_by_asset_id(id)
    return APIResponse(
        success=True,
        data=AdminSourcePriceOut.from_objs(result.data),
        meta=result.meta,
    )


@router.get(
    "/{id:int}/chart",
    response_model=AssetChartResponse,
)
async def get_asset_chart(
    id: AssetID,
    type: ChartType,
    service: FromDishka[IPriceTickerService],
) -> AssetChartResponse:
    """
    Draw an asset's series over the window the chart type names.
    """
    result = await service.get_chart(id, type)
    return APIResponse(
        success=True,
        data=result.data,
        meta=result.meta,
    )


@router.get(
    "/{id:int}/price/{symbol_code}",
    response_model=AssetPriceResponse,
)
async def get_asset_price_on_symbol(
    id: AssetID,
    symbol_code: SymbolCode,
    service: FromDishka[ISymbolConverterService],
) -> AssetPriceResponse:
    """
    Read an asset's settled price, stated on the symbol asked for.

    A symbol that weighs no gold, or one needing a dollar price there is none
    of, answers 400.
    """
    price = await service.convert_asset(id, symbol_code)
    return APIResponse.from_data(AssetPriceOut.from_obj(price))


@router.get(
    "/{id:int}/sources/{symbol_code}",
    response_model=AssetSourcePriceResponse,
)
async def get_asset_source_prices_on_symbol(
    id: AssetID,
    symbol_code: SymbolCode,
    service: FromDishka[ISymbolConverterService],
) -> AssetSourcePriceResponse:
    """
    Read what every source of one asset last quoted, all restated on the symbol
    asked for, so readings taken on different symbols compare.
    """
    prices = await service.convert_all_sources_of_asset(id, symbol_code)
    return APIResponse.from_data(AdminSourcePriceOut.from_objs(prices))


@router.get(
    "/batch",
    response_model=AssetResponse,
)
async def get_assets_batch(
    ids: Annotated[list[AssetIDInput], Query(default_factory=list)],
    service: FromDishka[IAssetService],
) -> AssetResponse:
    """
    Read many assets by id, in one request.

    An id nothing answers to is not an error for the whole call: what was
    found comes back as data, and the rest as errors beside it.
    """
    batch = await service.get_batch(ids)
    return APIResponse.from_data(
        AssetOut.from_objs(batch.items), errors=batch.errors
    )
