from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Response
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.stats.domain.models import PricingStatistics
from src.modules.pricing.stats.interfaces import IPricingStatisticsQuery

router = APIRouter(
    prefix="/internal/pricing/panel/pricing/stats",
    tags=["Panel Pricing Statistics"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)
StatisticsResponse = APIResponse[PricingStatistics, None]


@router.get("", response_model=StatisticsResponse)
async def statistics(
    response: Response, query: FromDishka[IPricingStatisticsQuery]
) -> StatisticsResponse:
    """Read complete current pricing counts without entity pages."""
    response.headers["Cache-Control"] = "no-store"
    result = await query.get()
    return APIResponse.from_data(result)
