from abc import ABC, abstractmethod
from typing import Sequence

import httpx
from papilio.core.logger import logger

from src.modules.pricing.engine.app.helpers.responses import (
    http_error,
    logical_error,
)
from src.modules.pricing.engine.domain.quotes import (
    ErrorQuote,
)
from src.modules.pricing.engine.infra.http import PriceHTTPGateway
from src.modules.pricing.sources.domain.enums import SourceCode
from src.shared.http import SourceHTTPClient


class AbstractFetcher[TQuote](ABC):
    __url__: str = ""
    __code__: SourceCode
    fee: float

    default_timeout: float | None = 10

    def __init__(
        self,
        connection: SourceHTTPClient,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        configuration: dict | None = None,
    ) -> None:
        self.configured = bool(configuration)
        configuration = configuration or {}
        self.__url__ = configuration.get("endpoint", "")
        self.http = PriceHTTPGateway(
            connection,
            headers or {},
            timeout or 10,
            set(configuration.get("allowed_hosts", [])),
        )
        for name, value in configuration.get("parameters", {}).items():
            if name not in self.parameter_names:
                raise ValueError("Unsupported price source parameter")
            setattr(self, name, value)

    parameter_names: set[str] = set()

    async def fetch(self) -> Sequence[TQuote]:
        try:
            if not self.configured:
                raise ValueError("Price source endpoint is not configured")
            resp = await self._request()
            resp.raise_for_status()
            quotes = self._parse(resp)
        except httpx.HTTPError as exc:
            logger.warning(
                "price source %s failed: %s", self.__code__, type(exc).__name__
            )
            quotes = self._failed(http_error(exc))
        except Exception as exc:
            logger.warning(
                "price source %s could not be read: %s",
                self.__code__,
                type(exc).__name__,
            )
            quotes = self._failed(logical_error(exc))
        return quotes

    async def _request(self) -> httpx.Response:
        response = await self.http.request(self.__url__)
        return response

    @abstractmethod
    def _parse(self, resp: httpx.Response) -> Sequence[TQuote]: ...

    @abstractmethod
    def _failed(self, error: ErrorQuote) -> Sequence[TQuote]: ...
