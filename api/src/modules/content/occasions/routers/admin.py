from datetime import date

from amupouya_calendar.models import CalendarPolicy
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.content.occasions.domain.dtos import (
    OccasionUpdate,
    OccasionWrite,
)
from src.modules.content.occasions.interfaces import (
    IOccasionQueries,
    IOccasionService,
)

router = APIRouter(
    prefix="/internal/occasions",
    tags=["Occasions"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)


@router.get("")
async def search(
    service: FromDishka[IOccasionService],
    query: str = Query(default="", max_length=250),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    result = await service.search(query, page, per_page)
    return APIResponse.from_data(result)


@router.post("/day/{target}")
async def day(
    target: date,
    policy: CalendarPolicy,
    queries: FromDishka[IOccasionQueries],
    timezone: str = "Asia/Tehran",
):
    result = await queries.day(target, policy, timezone)
    return APIResponse.from_data(result)


@router.get("/{key}")
async def get(key: str, service: FromDishka[IOccasionService]):
    result = await service.get(key)
    return APIResponse.from_data(result)


@router.post("")
async def create(data: OccasionWrite, service: FromDishka[IOccasionService]):
    result = await service.create(data)
    return APIResponse.from_data(result)


@router.put("/{key}")
async def update(
    key: str, data: OccasionUpdate, service: FromDishka[IOccasionService]
):
    result = await service.update(key, data)
    return APIResponse.from_data(result)
