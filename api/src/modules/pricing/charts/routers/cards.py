import asyncio

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Response
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.config.dependencies import AssetID
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.domain.models import AssetChartCardOut
from src.modules.pricing.charts.interfaces import IAssetChartQuery

router = APIRouter(
    prefix="/internal/pricing/chart-cards",
    tags=["Asset chart cards"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)


@router.get("", response_model=APIResponse[AssetChartCardOut, None])
async def get_cards(query: FromDishka[IAssetChartQuery]):
    cards = await query.get_all()
    return APIResponse(
        success=True,
        data=[
            AssetChartCardOut.model_validate(card, from_attributes=True)
            for card in cards
        ],
    )


@router.get("/{id:int}/image")
async def get_card_image(
    id: AssetID,
    query: FromDishka[IAssetChartQuery],
    renderer: FromDishka[AssetChartRenderer],
):
    card = await query.get(id)
    image = await asyncio.to_thread(renderer.render, card)
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
