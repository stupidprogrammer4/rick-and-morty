from abc import ABC, abstractmethod

import httpx
from papilio.core.logger import logger

from src.modules.pricing.engine.infra.http import PriceHTTPGateway
from src.modules.pricing.logins.domain.context import LoginContext
from src.modules.pricing.logins.domain.quotes import LoginError, LoginQuote
from src.modules.pricing.sources.domain.enums import ErrorType, SourceCode
from src.shared.http import SourceHTTPClient


class AbstractLogin(ABC):
    timeout = 30.0

    def __init__(self, source: LoginContext, client: SourceHTTPClient) -> None:
        super().__init__()
        self.source = source
        self.http = PriceHTTPGateway(
            client,
            {},
            self.timeout,
            set(source.login.get("allowed_hosts", [])),
        )

    async def login(self) -> LoginQuote:
        """
        Desc: Sign in to the source and answer with a quote, never raising.
        Returns:
            return (LoginQuote): Granted credentials, or the refusal.
        """
        try:
            credentials = await self._issue()
            quote = LoginQuote.granted(
                self.source.code, self.source.id, credentials
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "source login %s failed: %s",
                self.source.code,
                type(exc).__name__,
            )
            quote = self._refused(ErrorType.HTTP_ERROR, exc)
        except Exception as exc:
            logger.warning(
                "source login %s failed: %s",
                self.source.code,
                type(exc).__name__,
            )
            quote = self._refused(ErrorType.LOGICAL_ERROR, exc)
        return quote

    def _refused(self, kind: ErrorType, exc: Exception) -> LoginQuote:
        quote = LoginQuote.refused(
            self.source.code,
            self.source.id,
            LoginError(
                error_type=kind,
                message=type(exc).__name__,
            ),
        )
        return quote

    @abstractmethod
    async def _issue(self) -> dict[str, str]: ...


class MirrokniLogin(AbstractLogin):
    async def _issue(self) -> dict[str, str]:
        configuration = self.source.login
        secret = self.source.auth_credentials
        payload = {
            "CaptchaToken": "",
            "UserName": secret.get("username", ""),
            "Password": secret.get("password", ""),
            "RememberMe": False,
        }
        response = await self.http.post(
            configuration["login_url"], json=payload
        )
        data = response.json()["Data"]
        if data.get("user") is None:
            response = await self.http.post(
                configuration["end_sessions_url"], json=payload
            )
            data = response.json()["Data"]
        token = data["user"]["token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "shopkeeperid": configuration["shopkeeper_id"],
        }
        self.http.headers = headers
        profile = (await self.http.get(configuration["profile_url"])).json()
        headers["SessionId"] = profile["Data"]["SessionId"]
        return headers


LOGINS: dict[SourceCode, type[AbstractLogin]] = {
    SourceCode.MIRROKNI: MirrokniLogin,
}
