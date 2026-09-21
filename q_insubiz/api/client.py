from __future__ import annotations

import json
import logging
from typing import Any

from playwright.async_api import APIResponse

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)


logger = logging.getLogger(__name__)


class InsubizApiClient:
    """
    Generel API-klient til Insubiz.

    API-klienten anvender Playwrights request-context,
    som deler cookies med den browser-context, der blev
    brugt til login.
    """

    BASE_URL = "https://start.insubiz.dk"

    REQUEST_TIMEOUT_MS = 30_000
    DOWNLOAD_TIMEOUT_MS = 60_000

    ALLOWED_METHODS = frozenset(
        {
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
    )

    DOWNLOAD_METHODS = frozenset(
        {
            "GET",
            "POST",
        }
    )

    JSON_ACCEPT_HEADER = (
        "application/json, text/plain, */*"
    )

    DOWNLOAD_ACCEPT_HEADER = (
        "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet, "
        "application/vnd.ms-excel, "
        "text/csv, "
        "application/octet-stream"
    )

    def __init__(
        self,
        auth_manager: InsubizAuthManager,
    ) -> None:
        if not isinstance(
            auth_manager,
            InsubizAuthManager,
        ):
            raise TypeError(
                "auth_manager skal være en "
                "InsubizAuthManager."
            )

        self._auth_manager = auth_manager

    # --------------------------------------------------
    # URL og metode
    # --------------------------------------------------
    def _create_url(
        self,
        endpoint: str,
    ) -> str:
        """Opretter den komplette URL til API-kaldet."""
        if not isinstance(endpoint, str):
            raise TypeError(
                "endpoint skal være en tekstværdi."
            )

        normalized_endpoint = endpoint.strip()

        if not normalized_endpoint:
            raise ValueError(
                "endpoint må ikke være tom."
            )

        if normalized_endpoint.startswith(
            (
                "https://",
                "http://",
            )
        ):
            return normalized_endpoint

        return (
            f"{self.BASE_URL}/"
            f"{normalized_endpoint.lstrip('/')}"
        )

    def _normalize_method(
        self,
        method: str,
    ) -> str:
        """Validerer og normaliserer HTTP-metoden."""
        if not isinstance(method, str):
            raise TypeError(
                "method skal være en tekstværdi."
            )

        normalized_method = method.strip().upper()

        if normalized_method not in self.ALLOWED_METHODS:
            raise ValueError(
                "HTTP-metoden understøttes ikke. "
                f"Modtog: {method!r}. "
                "Tilladte metoder: "
                f"{sorted(self.ALLOWED_METHODS)!r}."
            )

        return normalized_method

    # --------------------------------------------------
    # Request-indstillinger
    # --------------------------------------------------
    def _create_request_options(
        self,
        *,
        method: str,
        params: dict[str, Any] | None,
        json_body: Any,
        download: bool,
    ) -> dict[str, Any]:
        """Opretter options til Playwright fetch()."""
        headers = {
            "Accept": (
                self.DOWNLOAD_ACCEPT_HEADER
                if download
                else self.JSON_ACCEPT_HEADER
            ),
            "Referer": f"{self.BASE_URL}/",
        }

        request_options: dict[str, Any] = {
            "method": method,
            "params": params,
            "headers": headers,
            "timeout": (
                self.DOWNLOAD_TIMEOUT_MS
                if download
                else self.REQUEST_TIMEOUT_MS
            ),
        }

        if json_body is not None:
            headers["Content-Type"] = (
                "application/json; charset=utf-8"
            )
            request_options["data"] = json.dumps(
                json_body,
                ensure_ascii=False,
            )

        return request_options

    # --------------------------------------------------
    # Fælles transport
    # --------------------------------------------------
    async def _send_request(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        download: bool = False,
    ) -> APIResponse:
        """Sender ét request gennem den aktive session."""
        normalized_method = self._normalize_method(
            method
        )
        url = self._create_url(endpoint)

        request_context = (
            await self._auth_manager
            .get_request_context()
        )

        request_options = self._create_request_options(
            method=normalized_method,
            params=params,
            json_body=json_body,
            download=download,
        )

        logger.info(
            "Sender %s til Insubiz: %s.",
            normalized_method,
            url,
        )

        try:
            return await request_context.fetch(
                url,
                **request_options,
            )
        except Exception as error:
            logger.exception(
                "Insubiz-requestet kunne ikke udføres. "
                "Metode: %s. Endpoint: %s.",
                normalized_method,
                endpoint,
            )
            raise RuntimeError(
                "Insubiz-requestet kunne ikke udføres. "
                f"Metode: {normalized_method}. "
                f"Endpoint: {endpoint}."
            ) from error

    async def _send_with_refresh(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        download: bool = False,
    ) -> APIResponse:
        """
        Sender et request og fornyer sessionen én gang
        ved HTTP 401 eller 403.
        """
        response = await self._send_request(
            method=method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
            download=download,
        )

        if response.status not in {
            401,
            403,
        }:
            return response

        logger.warning(
            "Insubiz-sessionen er udløbet. "
            "Fornyer login og forsøger requestet igen. "
            "Metode: %s. Endpoint: %s. "
            "HTTP-status: %s.",
            method,
            endpoint,
            response.status,
        )

        await self._auth_manager.refresh()

        return await self._send_request(
            method=method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
            download=download,
        )

    # --------------------------------------------------
    # JSON-response
    # --------------------------------------------------
    async def _request(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        """Udfører et API-kald og returnerer JSON."""
        normalized_method = self._normalize_method(
            method
        )

        response = await self._send_with_refresh(
            method=normalized_method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
            download=False,
        )

        return await self._parse_json_response(
            response=response,
            method=normalized_method,
            endpoint=endpoint,
        )

    async def _parse_json_response(
        self,
        *,
        response: APIResponse,
        method: str,
        endpoint: str,
    ) -> Any:
        """Kontrollerer statuskoden og returnerer JSON."""
        if not response.ok:
            response_text = await response.text()

            raise RuntimeError(
                "Insubiz API-kaldet fejlede. "
                f"Metode: {method}. "
                f"Endpoint: {endpoint}. "
                f"HTTP-status: {response.status}. "
                f"Response: {response_text[:500]}"
            )

        if response.status == 204:
            return None

        response_text = await response.text()

        if not response_text.strip():
            return None

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Insubiz returnerede ikke JSON. "
                f"Metode: {method}. "
                f"Endpoint: {endpoint}. "
                f"HTTP-status: {response.status}. "
                f"Response: {response_text[:500]}"
            ) from error

    # --------------------------------------------------
    # Public JSON-metoder
    # --------------------------------------------------
    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Sender et GET-kald til Insubiz."""
        return await self._request(
            method="GET",
            endpoint=endpoint,
            params=params,
        )

    async def post(
        self,
        endpoint: str,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Sender et POST-kald til Insubiz."""
        return await self._request(
            method="POST",
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

    async def put(
        self,
        endpoint: str,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Sender et PUT-kald til Insubiz."""
        return await self._request(
            method="PUT",
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

    async def patch(
        self,
        endpoint: str,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Sender et PATCH-kald til Insubiz."""
        return await self._request(
            method="PATCH",
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

    async def delete(
        self,
        endpoint: str,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Sender et DELETE-kald til Insubiz."""
        return await self._request(
            method="DELETE",
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

    # --------------------------------------------------
    # Download
    # --------------------------------------------------
    async def download(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> tuple[bytes, str]:
        """
        Henter en fil fra Insubiz.

        Returnerer filens binære indhold og response-headerens
        Content-Type.
        """
        normalized_method = self._normalize_method(
            method
        )

        if normalized_method not in self.DOWNLOAD_METHODS:
            raise ValueError(
                "Download-metoden skal være GET eller POST."
            )

        response = await self._send_with_refresh(
            method=normalized_method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
            download=True,
        )

        if not response.ok:
            response_text = await response.text()

            raise RuntimeError(
                "Insubiz-eksporten fejlede. "
                f"Metode: {normalized_method}. "
                f"Endpoint: {endpoint}. "
                f"HTTP-status: {response.status}. "
                f"Response: {response_text[:500]}"
            )

        content = await response.body()

        if not content:
            raise RuntimeError(
                "Insubiz-eksporten returnerede en tom fil."
            )

        content_type = (
            response.headers.get(
                "content-type",
                "",
            )
            or ""
        )

        logger.info(
            "Download gennemført. "
            "Endpoint: %s. Content-Type: %s. "
            "Filstørrelse: %s bytes.",
            endpoint,
            content_type or "ukendt",
            len(content),
        )

        return content, content_type

    # --------------------------------------------------
    # Oprydning
    # --------------------------------------------------
    async def close(self) -> None:
        """Lukker browseren og den autentificerede session."""
        await self._auth_manager.close()


__all__ = [
    "InsubizApiClient",
]
