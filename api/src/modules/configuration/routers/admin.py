from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse

from portal_contracts.configuration import (
    BotConfiguration,
    EntityWritten,
    SettingDefinitionCreate,
    SettingDefinitionOut,
    SettingKey,
    SettingSchemaOut,
    SettingScope,
    SettingValueOut,
    SettingValueWrite,
)
from src.config.security import owner_auth, service_auth
from src.modules.configuration.app.validation import SettingValueValidator
from src.modules.configuration.domain.dtos import (
    NewsSourceConfigWrite,
    NewsSourceCreate,
    NewsSourcePage,
    NewsSourceUpdate,
)
from src.modules.configuration.interfaces import (
    IConfigurationCommands,
    IConfigurationQueries,
    INewsSourceConfigService,
    INewsSourceService,
    ISettingDefinitionService,
    ISettingValueService,
)

router = APIRouter(
    prefix="/internal/configuration",
    tags=["Configuration"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)


@router.get(
    "/definitions",
    response_model=APIResponse[SettingDefinitionOut, None],
)
async def definitions(service: FromDishka[ISettingDefinitionService]):
    result = await service.all()
    return APIResponse.from_data(result)


@router.post(
    "/definitions", response_model=APIResponse[SettingDefinitionOut, None]
)
async def create_definition(
    data: SettingDefinitionCreate,
    service: FromDishka[ISettingDefinitionService],
):
    result = await service.create(data)
    return APIResponse.from_data(result)


@router.get("/values", response_model=APIResponse[SettingValueOut, None])
async def values(queries: FromDishka[IConfigurationQueries]):
    result = await queries.editable()
    return APIResponse.from_data(result)


@router.get("/schema/{key}")
async def schema(key: SettingKey) -> APIResponse[SettingSchemaOut, None]:
    return APIResponse.from_data(
        SettingSchemaOut(schema_definition=SettingValueValidator().schema(key))
    )


@router.get(
    "/values/{key}/{scope}", response_model=APIResponse[SettingValueOut, None]
)
async def value(
    key: SettingKey,
    scope: SettingScope,
    service: FromDishka[ISettingValueService],
):
    result = await service.get(key, scope)
    return APIResponse.from_data(result)


@router.put(
    "/values/{key}/{scope}", response_model=APIResponse[SettingValueOut, None]
)
async def write_value(
    key: SettingKey,
    scope: SettingScope,
    data: SettingValueWrite,
    service: FromDishka[ISettingValueService],
):
    result = await service.write(key, scope, data)
    return APIResponse.from_data(result)


@router.get("/bot", response_model=APIResponse[BotConfiguration, None])
async def bot_configuration(queries: FromDishka[IConfigurationQueries]):
    result = await queries.snapshot()
    return APIResponse.from_data(
        BotConfiguration(
            channel_id=result.configuration.portal.channel_id,
            presentation=result.presentation,
        )
    )


@router.get("/sources", response_model=APIResponse[NewsSourcePage, None])
async def sources(
    queries: FromDishka[IConfigurationQueries],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    result = await queries.sources(page, per_page)
    return APIResponse.from_data(result)


@router.post("/sources", response_model=APIResponse[EntityWritten, None])
async def create_source(
    data: NewsSourceCreate, commands: FromDishka[IConfigurationCommands]
):
    result = await commands.create_source(data)
    return APIResponse.from_data(EntityWritten(id=result))


@router.put(
    "/sources/{id:int}", response_model=APIResponse[EntityWritten, None]
)
async def update_source(
    id: int, data: NewsSourceUpdate, service: FromDishka[INewsSourceService]
):
    result = await service.update(id, data)
    return APIResponse.from_data(EntityWritten(id=result.id))


@router.put(
    "/sources/{id:int}/config", response_model=APIResponse[EntityWritten, None]
)
async def update_source_config(
    id: int,
    data: NewsSourceConfigWrite,
    service: FromDishka[INewsSourceConfigService],
):
    result = await service.update(id, data)
    return APIResponse.from_data(EntityWritten(id=result.source_id))
