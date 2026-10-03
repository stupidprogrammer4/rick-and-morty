from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.assets.interfaces import IAssetPriceQuery
from src.modules.pricing.assets.routers.schemas import AssetPriceSummaryOut

router = APIRouter(
    prefix="/internal/pricing/assets/prices",
    tags=["Assets"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

AssetPriceSummaryResponse = APIResponse[AssetPriceSummaryOut, None]


@router.get("", response_model=AssetPriceSummaryResponse)
async def get_prices(
    query: FromDishka[IAssetPriceQuery],
) -> AssetPriceSummaryResponse:
    """List the last settled prices, with asset codes only."""
    prices = await query.get_all()
    return APIResponse.from_data(AssetPriceSummaryOut.from_objs(prices))


@router.get("/{asset_code}", response_model=AssetPriceSummaryResponse)
async def get_price(
    asset_code: AssetCode,
    query: FromDishka[IAssetPriceQuery],
) -> AssetPriceSummaryResponse:
    """Read one settled price by asset code; missing prices return 404."""
    price = await query.get_by_code(asset_code)
    return APIResponse.from_data(AssetPriceSummaryOut.from_obj(price))
