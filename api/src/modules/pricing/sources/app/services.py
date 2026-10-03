from typing import Mapping, Sequence

from papilio.core import resources as framework_resources
from papilio.errors.exceptions import NotFoundException, ValidationException
from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional
from papilio.schemas.results import BatchResultType
from papilio.tools.checks import Checks, IDChecks

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.engine.interfaces import (
    ICacheReaderService as ISourceCacheReaderService,
)
from src.modules.pricing.sources.config.constants import SOURCE_ID_ENCRYPTION
from src.modules.pricing.sources.domain.dtos import (
    SourceConfigUpdate,
    SourceCreate,
    SourceUpdate,
)
from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.sources.domain.models import (
    AdminSourcePriceModel,
    SourceConfigModel,
    SourceMetaModel,
    SourceModel,
    SourceOnlyMetaModel,
    SourcesMetaModel,
)
from src.modules.pricing.sources.domain.results import (
    MultiSourcePricesResult,
    SourceErrorRemoval,
    SourcePricesResult,
)
from src.modules.pricing.sources.infra.mysql import (
    SourceConfigRepository,
    SourceRepository,
)
from src.modules.pricing.sources.interfaces import (
    ISourceService,
)
from src.modules.pricing.symbols.domain.models import (
    SymbolMetaModel,
    SymbolModel,
)
from src.modules.pricing.symbols.interfaces import (
    ISymbolMetaService,
    ISymbolService,
)


class SourceConfigService(Checks[SourceConfigModel]):
    entity = "SourceConfig"

    def __init__(
        self, repo: SourceConfigRepository, policy: MarketEnginePolicy
    ) -> None:
        self.repo = repo
        self.default_timeout = policy.source_timeout

    @handle_conflicts
    @transactional
    async def create_default(self, source_id: int) -> SourceConfigModel:
        """
        Desc: Create the default config of a newly created source.
        Args:
            source_id (int): ID of the owning source.
        Returns:
            return (SourceConfigModel): The created config.
        """
        config = await self.repo.create(
            SourceConfigModel(
                source_id=source_id, timeout=self.default_timeout
            )
        )
        return config

    @handle_conflicts
    @transactional
    async def create_defaults(
        self, source_ids: Sequence[int]
    ) -> Sequence[SourceConfigModel]:
        """Create default configurations in one write."""
        configs = await self.repo.bulk_create(
            [
                SourceConfigModel(
                    source_id=id,
                    timeout=self.default_timeout,
                )
                for id in source_ids
            ]
        )
        return configs

    @handle_conflicts
    @transactional
    async def update(
        self,
        source_id: int,
        data: SourceConfigUpdate,
    ) -> SourceConfigModel:
        """
        Desc: Patch a source's config.
        Args:
            source_id (int): ID of the owning source.
            data (SourceConfigUpdate): The fields to change.
        Returns:
            return (SourceConfigModel): The updated config.
        """
        row = self._check_not_empty_dict(data.to_row())
        config = await self.repo.update_by_source_id(source_id, row)
        config = self._check_for_existence("source_id", source_id, config)
        return config

    @handle_conflicts
    @transactional
    async def update_headers_credentials(
        self, credentials: Mapping[int, dict[str, str]]
    ) -> Sequence[SourceConfigModel]:
        """Replace headers atomically; every requested config must exist."""
        configs = await self.repo.update_headers_credentials(credentials)
        found = {config.source_id for config in configs}
        missing = next((id for id in credentials if id not in found), None)
        if missing is not None:
            self._check_for_existence("source_id", missing, None)
        return configs

    async def get_by_source_id(self, source_id: int) -> SourceConfigModel:
        """
        Desc: Get a source's config.
        Args:
            source_id (int): ID of the owning source.
        Returns:
            return (SourceConfigModel): The found config.
        """
        config = await self.repo.get_by_source_id(source_id)
        config = self._check_for_existence("source_id", source_id, config)
        return config

    async def get_all(self) -> Sequence[SourceConfigModel]:
        """
        Desc: Get every source config.
        Returns:
            return (Sequence[SourceConfigModel]): All configs.
        """
        configs = await self.repo.get_all()
        return configs


class SourceService(IDChecks[SourceModel]):
    entity = "Source"

    def __init__(
        self,
        repo: SourceRepository,
    ) -> None:
        self.repo = repo

    @handle_conflicts
    @transactional
    async def create(self, data: SourceCreate) -> SourceModel:
        """
        Desc: Create a source.
        Args:
            data (SourceCreate): Validated payload to persist.
        Returns:
            return (SourceModel): The created source.
        """
        source = await self.repo.create(
            SourceModel(**data.to_row(exclude_unset=False))
        )
        return source

    @handle_conflicts
    @transactional
    async def update(self, id: int, data: SourceUpdate) -> SourceModel:
        """
        Desc: Patch a source by id.
        Args:
            id (int): ID of the source.
            data (SourceUpdate): The fields to change.
        Returns:
            return (SourceModel): The updated source.
        """
        row = self._check_not_empty_dict(data.to_row())
        await self.repo.update_by_id(id, row)
        source = await self.repo.get_by_id(id)
        source = self._check_for_id_existence(id, source)
        return source

    async def get_by_id(self, id: int) -> SourceModel:
        """
        Desc: Get a source by id.
        Args:
            id (int): ID of the source.
        Returns:
            return (SourceModel): The found source.
        """
        source = await self.repo.get_by_id(id)
        source = self._check_for_id_existence(id, source)
        return source

    async def get_by_ids(
        self,
        ids: list[int],
    ) -> Sequence[SourceModel]:
        """
        Desc: Get the sources the given ids belong to.
        Args:
            ids (list[int]): IDs of the sources to read.
        Returns:
            return (Sequence[SourceModel]): The sources that exist.
        """
        sources = await self.repo.get_by_ids(ids)
        return sources

    async def get_all(self) -> Sequence[SourceModel]:
        """
        Desc: Get every source.
        Returns:
            return (Sequence[SourceModel]): All sources.
        """
        sources = await self.repo.get_all()
        return sources

    @handle_conflicts
    @transactional
    async def mark_failed(
        self,
        id: int,
        error: SourceErrorInfo,
    ) -> SourceModel:
        """
        Desc: Record why a source's last fetch failed.
        Args:
            id (int): ID of the source.
            error (SourceErrorInfo): What went wrong.
        Returns:
            return (SourceModel): The updated source.
        """
        await self.repo.update_by_id(id, {"error": error})
        source = await self.repo.get_by_id(id)
        source = self._check_for_id_existence(id, source)
        return source

    @handle_conflicts
    @transactional
    async def clear_error(self, id: int) -> SourceErrorRemoval:
        """Clear and return the recorded source error."""
        source = await self.repo.clear_error(id)
        source = self._check_for_id_existence(id, source)
        if source.error is None:
            raise NotFoundException(
                message="Source has no recorded error",
                message_code="source_error_not_found",
                entity="SourceError",
                identifier="source_id",
                identifier_value=id,
            )
        return SourceErrorRemoval(source_id=id, error=source.error)

    @handle_conflicts
    @transactional
    async def remove(self, id: int) -> SourceModel:
        """
        Desc: Delete a source by id, its config cascading with it.
        Args:
            id (int): ID of the source.
        Returns:
            return (SourceModel): The deleted source.
        """
        source = await self.repo.get_by_id(id)
        await self.repo.remove_by_id(id)
        source = self._check_for_id_existence(id, source)
        return source

    async def get_batch(
        self,
        ids: list[int],
    ) -> BatchResultType[SourceModel, ValidationException]:
        """
        Desc: Get many sources at once, saying which of the ids nothing
            answered to.
        Args:
            ids (list[int]): IDs of the sources.
        Returns:
            return (BatchResultType): What was found, and an error per id
                that was not.
        """
        found = await self.repo.get_by_ids(ids)
        batch = self._check_batch_data(ids, found)
        return batch


class SourceErrorService(IDChecks[SourceModel]):
    entity = "Source"

    def __init__(self, repo: SourceRepository) -> None:
        self.repo = repo

    @handle_conflicts
    @transactional
    async def apply_error(
        self, source_id: int, error: SourceErrorInfo | None
    ) -> SourceModel:
        await self.repo.update_by_id(
            source_id, SourceModel.patch(error=error).to_row()
        )
        source = await self.repo.get_by_id(source_id)
        source = self._check_for_id_existence(source_id, source)
        return source

    @handle_conflicts
    @transactional
    async def apply_errors(
        self,
        errors: Mapping[int, SourceErrorInfo | None],
    ) -> Sequence[SourceModel]:
        """
        Desc: Record what a crawl learned about every source it called.
        Args:
            errors (Mapping[int, SourceErrorInfo | None]): The failure of
                each source, or None where it answered.
        Returns:
            return (Sequence[SourceModel]): The updated sources.
        """
        rows = self._check_not_empty_dict(dict(errors))
        sources = await self.repo.update_errors(
            [
                SourceModel.patch(id=id, error=error)
                for id, error in rows.items()
            ]
        )
        return sources


class SourceMetaService:
    def __init__(
        self,
        sources: ISourceService,
        symbols: ISymbolService,
    ) -> None:
        self.sources = sources
        self.symbols = symbols

    def _meta(
        self,
        sources: Sequence[SourceModel],
        symbols: Sequence[SymbolModel],
    ) -> SourcesMetaModel:
        """
        Desc: Name the sources and lines already read.
        Args:
            sources (Sequence[SourceModel]): The sources to name.
            symbols (Sequence[SymbolModel]): The lines to name.
        Returns:
            return (SourcesMetaModel): One entry per source and per line.
        """
        return SourcesMetaModel(
            sources=SourceMetaModel.from_objs(sources),
            symbols=SymbolMetaModel.from_objs(symbols),
        )

    async def build(
        self,
        source_ids: Sequence[int],
        symbol_ids: Sequence[int],
    ) -> SourcesMetaModel:
        """
        Desc: Name the sources and lines the given ids belong to.
        Args:
            source_ids (Sequence[int]): IDs of the sources to name.
            symbol_ids (Sequence[int]): IDs of the lines to name.
        Returns:
            return (SourcesMetaModel): One entry per source and per line.
        """
        sources = await self.sources.get_by_ids(list(source_ids))
        symbols = await self.symbols.get_by_ids(list(symbol_ids))
        return self._meta(sources, symbols)

    async def build_by_sources(
        self,
        sources: Sequence[SourceModel],
        symbol_ids: Sequence[int],
    ) -> SourcesMetaModel:
        """
        Desc: Name the lines the given ids belong to, next to sources the
        caller already read.
        Args:
            sources (Sequence[SourceModel]): The sources to name.
            symbol_ids (Sequence[int]): IDs of the lines to name.
        Returns:
            return (SourcesMetaModel): One entry per source and per line.
        """
        symbols = await self.symbols.get_by_ids(list(symbol_ids))
        return self._meta(sources, symbols)

    async def build_by_symbols(
        self,
        source_ids: Sequence[int],
        symbols: Sequence[SymbolModel],
    ) -> SourcesMetaModel:
        """
        Desc: Name the sources the given ids belong to, next to lines the
        caller already read.
        Args:
            source_ids (Sequence[int]): IDs of the sources to name.
            symbols (Sequence[SymbolModel]): The lines to name.
        Returns:
            return (SourcesMetaModel): One entry per source and per line.
        """
        sources = await self.sources.get_by_ids(list(source_ids))
        return self._meta(sources, symbols)

    async def build_sources(
        self,
        source_ids: Sequence[int],
    ) -> SourceOnlyMetaModel:
        """
        Desc: Name the sources the given ids belong to, with no lines
            beside them.
        Args:
            source_ids (Sequence[int]): IDs of the sources to name.
        Returns:
            return (SourceOnlyMetaModel): One entry per source that exists.
        """
        sources = await self.sources.get_by_ids(list(source_ids))
        return SourceOnlyMetaModel(sources=SourceMetaModel.from_objs(sources))


class SourcePriceService:
    def __init__(
        self,
        readings: ISourceCacheReaderService,
        meta: ISymbolMetaService,
    ) -> None:
        self.readings = readings
        self.meta = meta

    async def get_by_source_id(self, source_id: int) -> SourcePricesResult:
        """
        Desc: Read everything one source last quoted, across every line.
        Args:
            source_id (int): ID of the source being asked about.
        Returns:
            return (SourcePricesResult): Its prices, and the lines they
                are of.
        """
        rows = list(await self.readings.get_by_source_id(source_id))
        if not rows:
            raise NotFoundException(
                identifier="source_id",
                identifier_value=SOURCE_ID_ENCRYPTION.encode(source_id),
                message="No source has priced anything under that id",
                message_code=framework_resources.NOT_FOUND_ERROR,
                entity="Price",
            )
        meta = await self.meta.build([row.symbol_id for row in rows])
        return SourcePricesResult(
            data=AdminSourcePriceModel.from_objs(rows), meta=meta
        )

    async def get_by_source_ids(
        self, source_ids: Sequence[int]
    ) -> MultiSourcePricesResult:
        """
        Desc: Read everything several sources last quoted, across every
            line, reaching only for their own fields.
        Args:
            source_ids (Sequence[int]): IDs of the sources being asked
                about.
        Returns:
            return (MultiSourcePricesResult): Their prices, and the lines
                the prices are of.
        """
        rows = list(await self.readings.get_by_source_ids(source_ids))
        meta = await self.meta.build(list({row.symbol_id for row in rows}))
        return MultiSourcePricesResult(
            data=AdminSourcePriceModel.from_objs(rows), meta=meta
        )
