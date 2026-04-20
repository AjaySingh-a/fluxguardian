from typing import Any

import httpx

from app.config import settings


class OpenMetadataClient:
    """Async client for the OpenMetadata REST API."""

    def __init__(
        self,
        host: str | None = None,
        jwt_token: str | None = None,
    ) -> None:
        self._base_url = (host or settings.openmetadata_host).rstrip("/")
        self._token = jwt_token or settings.openmetadata_jwt_token
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle helpers — use as an async context manager or call
    # open() / close() manually.
    # ------------------------------------------------------------------

    async def open(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=10.0,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "OpenMetadataClient":
        await self.open()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client is not open. Use 'async with' or call open() first.")
        return self._client

    async def _get(self, path: str, **kwargs: Any) -> Any:
        response = await self._http.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """GET /api/v1/system/version — returns OpenMetadata version info."""
        return await self._get("/api/v1/system/version")  # type: ignore[return-value]
