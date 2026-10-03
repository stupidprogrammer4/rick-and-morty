from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse
from papilio.core import resources as framework_resources
from papilio.errors.exceptions import NotFoundException

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.config.dependencies import AssetID
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.domain.models import AssetsMetaModel
from src.modules.pricing.assets.interfaces import (
    IAssetService,
    IAssetSourcePriceService,
)
from src.modules.pricing.assets.routers.schemas import (
    AssetOut,
    AssetPriceOut,
)
from src.modules.pricing.calculator.interfaces import (
    ICacheReaderService,
    ISymbolConverterService,
)
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.sources.routers.schemas import (
    SourcePriceOut,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import ChartOutputModel
from src.modules.pricing.ticker.interfaces import IPriceTickerService

router = APIRouter(
    prefix="/internal/pricing/assets",
    tags=["Assets"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

AssetResponse = APIResponse[AssetOut, None]
AssetPriceResponse = APIResponse[AssetPriceOut, None]
AssetChartResponse = APIResponse[ChartOutputModel, AssetsMetaModel]
AssetSourcePriceResponse = APIResponse[SourcePriceOut, SourcesMetaModel]


@router.get("", response_model=AssetResponse, response_model_exclude_none=True)
async def get_assets(
    service: FromDishka[IAssetService],
) -> AssetResponse:
    """
    List the assets the shop prices.
    """
    assets = await service.get_all()
    return APIResponse.from_data(AssetOut.from_objs(assets))


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
    Read what every source of one asset last quoted.
    """
    result = await service.get_by_asset_id(id)
    return APIResponse(
        success=True,
        data=SourcePriceOut.from_objs(result.data),
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
    asked for.
    """
    prices = await service.convert_all_sources_of_asset(id, symbol_code)
    return APIResponse.from_data(SourcePriceOut.from_objs(prices))
