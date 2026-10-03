from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.engine.interfaces import (
    IAggregatorService,
    ICacheReaderService,
)
from src.modules.pricing.engine.routers.schemas import (
    AggregatedPriceOut,
    PublicAssetBubblesOut,
    PublicBubbleOut,
    PublicPriceOut,
    PublicSymbolPricesOut,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode

router = APIRouter(
    prefix="/internal/pricing/prices",
    tags=["Prices"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

SymbolPricesResponse = APIResponse[PublicSymbolPricesOut, None]
AssetBubblesResponse = APIResponse[PublicAssetBubblesOut, None]
AggregatedPriceResponse = APIResponse[AggregatedPriceOut, None]


@router.get(
    "",
    response_model=SymbolPricesResponse,
)
async def get_prices(
    service: FromDishka[ICacheReaderService],
) -> SymbolPricesResponse:
    """
    Read what every asset last settled at, as the storefront shows it.
    """
    prices = await service.get_all()
    return APIResponse.from_data(
        [
            PublicSymbolPricesOut(
                symbol=symbol, prices=PublicPriceOut.from_objs(quotes)
            )
            for symbol, quotes in prices.items()
        ]
    )


@router.get(
    "/bubbles",
    response_model=AssetBubblesResponse,
)
async def get_bubbles(
    service: FromDishka[ICacheReaderService],
) -> AssetBubblesResponse:
    """
    Read the premium every asset last settled at.
    """
    bubbles = await service.get_all_bubbles()
    return APIResponse.from_data(
        [
            PublicAssetBubblesOut(
                asset=asset, bubbles=PublicBubbleOut.from_objs(rows)
            )
            for asset, rows in bubbles.items()
        ]
    )


@router.get(
    "/bubbles/{code}",
    response_model=AssetBubblesResponse,
)
async def get_asset_bubbles(
    code: AssetCode,
    service: FromDishka[ICacheReaderService],
) -> AssetBubblesResponse:
    """
    Read the premium every source last published for one asset.
    """
    rows = await service.get_bubbles_by_asset(code)
    return APIResponse.from_data(
        PublicAssetBubblesOut(
            asset=code, bubbles=PublicBubbleOut.from_objs(rows)
        )
    )


@router.get(
    "/{symbol}",
    response_model=SymbolPricesResponse,
)
async def get_symbol_prices(
    symbol: SymbolCode,
    service: FromDishka[ICacheReaderService],
) -> SymbolPricesResponse:
    """
    Read what every source last quoted on one symbol.
    """
    quotes = await service.get_by_symbol(symbol)
    return APIResponse.from_data(
        PublicSymbolPricesOut(
            symbol=symbol, prices=PublicPriceOut.from_objs(quotes)
        )
    )


@router.get(
    "/symbols/{code}/agg",
    response_model=AggregatedPriceResponse,
)
async def agg_symbol_prices(
    code: SymbolCode,
    service: FromDishka[IAggregatorService],
) -> AggregatedPriceResponse:
    """
    Fold what every source quoted on one symbol into a single price, by the
    rule that symbol's asset is aggregated under.
    """
    result = await service.agg(code)
    return APIResponse.from_data(AggregatedPriceOut.from_obj(result))
