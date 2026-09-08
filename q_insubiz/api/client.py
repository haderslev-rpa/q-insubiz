from typing import Any
import json
from playwright.async_api import APIResponse

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)


class InsubizApiClient:
    """
    Generel API-klient til Insubiz.

    API-klienten anvender Playwrights request-context,
    som deler cookies med den browser-context, der blev
    brugt til login.
    """

    BASE_URL = "https://start.insubiz.dk"

    def __init__(
        self,
        auth_manager: InsubizAuthManager,
    ) -> None:
        self._auth_manager = auth_manager

    def _create_url(
        self,
        endpoint: str,
    ) -> str:
        """
        Opretter den komplette URL til API-kaldet.
        """

        if not isinstance(endpoint, str):
            raise TypeError(
                "endpoint skal være en tekstværdi."
            )

        normalized_endpoint = endpoint.strip()

        if not normalized_endpoint:
            raise ValueError(
                "endpoint må ikke være tom."
            )

        # Tillad komplette URL'er.
        if normalized_endpoint.startswith(
            ("https://", "http://")
        ):
            return normalized_endpoint

        if not normalized_endpoint.startswith("/"):
            normalized_endpoint = (
                f"/{normalized_endpoint}"
            )

        return (
            f"{self.BASE_URL}"
            f"{normalized_endpoint}"
        )

    async def _send_request(
        self,
        method: str,
        endpoint: str,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> APIResponse:
        """
        Sender en almindelig API-request gennem den
        autentificerede Playwright-context.
        """

        request_context = (
            await self._auth_manager
            .get_request_context()
        )

        url = self._create_url(endpoint)

        print(
            f"Sender {method} til Insubiz: {url}"
        )

        return await request_context.fetch(
            url,
            method=method,
            params=params,
            data=json_body,
            headers={
                "Accept": "application/json",
                "Referer": "https://start.insubiz.dk/",
            },
            timeout=30_000,
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        """
        Udfører et almindeligt API-kald.

        Ved HTTP 401 eller 403 fornyes login,
        hvorefter API-kaldet forsøges én gang mere.
        """

        response = await self._send_request(
            method=method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

        if response.status in {
            401,
            403,
        }:
            print(
                "Insubiz-sessionen er udløbet. "
                "Logger ind igen..."
            )

            await self._auth_manager.refresh()

            response = await self._send_request(
                method=method,
                endpoint=endpoint,
                params=params,
                json_body=json_body,
            )

        return await self._parse_json_response(
            response=response,
            method=method,
            endpoint=endpoint,
        )

    async def _parse_json_response(
        self,
        response: APIResponse,
        method: str,
        endpoint: str,
    ) -> Any:
        """
        Kontrollerer statuskoden og returnerer JSON.
        """

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

        try:
            return await response.json()

        except Exception as error:
            response_text = await response.text()

            raise RuntimeError(
                "Insubiz returnerede ikke JSON. "
                f"Metode: {method}. "
                f"Endpoint: {endpoint}. "
                f"HTTP-status: {response.status}. "
                f"Response: {response_text[:500]}"
            ) from error

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Sender et GET-kald til Insubiz.
        """

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
        """
        Sender et POST-kald til Insubiz.
        """

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
        """
        Sender et PUT-kald til Insubiz.
        """

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
        """
        Sender et PATCH-kald til Insubiz.
        """

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
        """
        Sender et DELETE-kald til Insubiz.
        """

        return await self._request(
            method="DELETE",
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

    async def _send_download_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> APIResponse:
        """
        Sender en request, som forventes at returnere
        en fil i stedet for JSON.
        """

        request_context = (
            await self._auth_manager
            .get_request_context()
        )

        headers = {
            "Accept": (
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet, "
                "application/vnd.ms-excel, "
                "text/csv, "
                "application/octet-stream"
            ),
            "Referer": "https://start.insubiz.dk/",
        }

        request_options: dict[str, Any] = {
            "method": method,
            "params": params,
            "headers": headers,
            "timeout": 60_000,
        }

        # Content-Type og body medsendes kun,
        # når endpointet faktisk har en JSON-body.
        if json_body is not None:
            headers["Content-Type"] = (
                "application/json; charset=utf-8"
            )

            request_options["data"] = json.dumps(
                json_body,
                ensure_ascii=False,
            )

        return await request_context.fetch(
            self._create_url(endpoint),
            **request_options,
        )
    
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

        Output:
        - Filens binære indhold.
        - Response-headerens Content-Type.
        """

        normalized_method = method.strip().upper()

        if normalized_method not in {
            "GET",
            "POST",
        }:
            raise ValueError(
                "Download-metoden skal være GET eller POST."
            )

        response = await self._send_download_request(
            method=normalized_method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

        if response.status in {
            401,
            403,
        }:
            print(
                "Insubiz-sessionen er udløbet. "
                "Logger ind igen..."
            )

            await self._auth_manager.refresh()

            response = await self._send_download_request(
                method=normalized_method,
                endpoint=endpoint,
                params=params,
                json_body=json_body,
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

        content_type = (
            response.headers.get(
                "content-type",
                "",
            )
            or ""
        )

        content = await response.body()

        if not content:
            raise RuntimeError(
                "Insubiz-eksporten returnerede en tom fil."
            )

        print(
            "Download gennemført. "
            f"Content-Type: {content_type or 'ukendt'}. "
            f"Filstørrelse: {len(content)} bytes."
        )

        return content, content_type

    async def close(self) -> None:
        """
        Lukker browseren og den autentificerede session.
        """

        await self._auth_manager.close()