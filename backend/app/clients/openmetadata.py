import logging
import time
from collections import deque
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Simple TTL cache: cache_key → (result, expires_at)
_lineage_cache: dict[tuple, tuple[Any, float]] = {}
_LINEAGE_TTL = 60.0  # seconds


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
            timeout=30.0,
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
        t0 = time.monotonic()
        response = await self._http.get(path, **kwargs)
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.debug("GET %s → %d (%.1f ms)", path, response.status_code, elapsed_ms)
        response.raise_for_status()
        return response.json()

    async def _get_or_none(
        self,
        path: str,
        not_found_codes: tuple[int, ...] = (404,),
        **kwargs: Any,
    ) -> Any | None:
        """Like _get but returns None for not_found_codes instead of raising."""
        t0 = time.monotonic()
        response = await self._http.get(path, **kwargs)
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.debug("GET %s → %d (%.1f ms)", path, response.status_code, elapsed_ms)
        if response.status_code in not_found_codes:
            return None
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """GET /api/v1/system/version — returns OpenMetadata version info."""
        return await self._get("/api/v1/system/version")  # type: ignore[return-value]

    async def get_table_by_fqn(self, fqn: str) -> dict | None:
        """
        GET /api/v1/tables/name/{fqn}?fields=columns,owners,tags
        Returns full table dict including columns, owners, and tags.
        Returns None if the table does not exist (404).

        FQN format: ServiceName.databaseName.schemaName.tableName
        e.g. "FoodieExpressPostgres.foodieexpress.public.users"
        """
        path = f"/api/v1/tables/name/{fqn}"
        # Note: OM uses "owners" (plural) not "owner" in v1.x
        params = {"fields": "columns,owners,tags"}
        return await self._get_or_none(path, params=params)

    async def get_column_lineage(
        self,
        entity_fqn: str,
        upstream_depth: int = 1,
        downstream_depth: int = 3,
        entity_type: str = "table",
    ) -> dict:
        """
        GET /api/v1/lineage/{entity_type}/name/{fqn}
        Returns the lineage graph with 'entity', 'nodes', 'upstreamEdges',
        and 'downstreamEdges' keys.
        Results are cached in memory for 60 seconds.
        """
        cache_key = (entity_fqn, upstream_depth, downstream_depth, entity_type)
        now = time.monotonic()

        cached = _lineage_cache.get(cache_key)
        if cached is not None:
            result, expires_at = cached
            if now < expires_at:
                logger.debug("lineage cache hit for %s", entity_fqn)
                return result

        path = f"/api/v1/lineage/{entity_type}/name/{entity_fqn}"
        params: dict[str, Any] = {
            "upstreamDepth": upstream_depth,
            "downstreamDepth": downstream_depth,
        }
        data = await self._get(path, params=params)
        _lineage_cache[cache_key] = (data, now + _LINEAGE_TTL)
        return data  # type: ignore[return-value]

    async def get_downstream_assets(self, column_fqn: str) -> list[dict]:
        """
        Walk the lineage graph downstream from a column FQN and return a flat
        list of unique downstream assets (tables, dashboards, ML models,
        pipelines, etc.).

        Each entry: {id, name, fullyQualifiedName, type, owner_name,
                     owner_email, depth, tags}

        Column FQN format: ServiceName.database.schema.table.column
        """
        # Lineage API works at the table level; strip the column segment.
        parts = column_fqn.rsplit(".", 1)
        table_fqn = parts[0] if len(parts) == 2 else column_fqn

        try:
            graph = await self.get_column_lineage(
                table_fqn, upstream_depth=0, downstream_depth=5, entity_type="table"
            )
        except httpx.HTTPStatusError:
            logger.warning("Could not fetch lineage for %s", table_fqn)
            return []

        # Build a lookup of node id → node metadata
        nodes: dict[str, dict] = {}
        for node in graph.get("nodes", []):
            node_id = node.get("id", "")
            if node_id:
                nodes[node_id] = node

        # Also index the root entity itself
        root_entity = graph.get("entity", {})
        root_id: str = root_entity.get("id", "")
        if root_id and root_id not in nodes:
            nodes[root_id] = root_entity

        # Build downstream adjacency list from downstreamEdges.
        # Each edge: {"fromEntity": "<uuid>", "toEntity": "<uuid>", ...}
        adjacency: dict[str, list[str]] = {}
        for edge in graph.get("downstreamEdges", []):
            from_id = edge.get("fromEntity", "")
            to_id = edge.get("toEntity", "")
            if from_id and to_id:
                adjacency.setdefault(from_id, []).append(to_id)

        if not root_id:
            return []

        # BFS downstream
        visited: set[str] = {root_id}
        queue: deque[tuple[str, int]] = deque([(root_id, 0)])
        results: list[dict] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth > 0:
                node = nodes.get(current_id, {})
                owner_name, owner_email = self._extract_owner(node)
                results.append(
                    {
                        "id": current_id,
                        "name": node.get("name", ""),
                        "fullyQualifiedName": node.get("fullyQualifiedName", ""),
                        "type": node.get("type", node.get("entityType", "")),
                        "owner_name": owner_name,
                        "owner_email": owner_email,
                        "depth": depth,
                        "tags": self._extract_tag_names(node.get("tags", [])),
                    }
                )
            for neighbor_id in adjacency.get(current_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

        return results

    def _extract_owner(self, node: dict) -> tuple[str, str]:
        """Return (owner_name, owner_email) from a node dict.
        OM v1.x stores owners as a list under the 'owners' key."""
        owners = node.get("owners") or node.get("owner") or []
        if isinstance(owners, dict):
            owners = [owners]
        if owners:
            first = owners[0]
            return first.get("name", ""), first.get("email", "")
        return "", ""

    def _extract_tag_names(self, tags: list[dict]) -> list[str]:
        return [t.get("tagFQN", t.get("name", "")) for t in tags if t]

    async def get_entity_owner(self, entity_id: str, entity_type: str) -> dict | None:
        """
        GET /api/v1/{entity_type}/{entity_id}?fields=owners
        Returns {id, name, email} for the first owner, or None.
        entity_type examples: "tables", "dashboards", "pipelines"
        """
        path = f"/api/v1/{entity_type}/{entity_id}"
        data = await self._get_or_none(path, params={"fields": "owners"})
        if data is None:
            return None
        owners = data.get("owners") or data.get("owner") or []
        if isinstance(owners, dict):
            owners = [owners]
        if not owners:
            return None
        first = owners[0]
        return {
            "id": first.get("id", ""),
            "name": first.get("name", ""),
            "email": first.get("email", ""),
        }

    async def get_column_tags(self, table_fqn: str, column_name: str) -> list[str]:
        """
        Return a list of tag FQNs applied to the specified column.
        Column tags are embedded in the 'columns' response field.
        """
        path = f"/api/v1/tables/name/{table_fqn}"
        data = await self._get_or_none(path, params={"fields": "columns"})
        if data is None:
            return []
        for col in data.get("columns", []):
            if col.get("name") == column_name:
                return self._extract_tag_names(col.get("tags", []))
        return []

    async def is_pii_column(self, table_fqn: str, column_name: str) -> bool:
        """
        Returns True if the column has any tag whose FQN starts with "PII."
        (e.g. "PII.Email", "PII.Phone", "PII.Financial").
        """
        tags = await self.get_column_tags(table_fqn, column_name)
        return any(t.upper().startswith("PII.") or t.upper() == "PII" for t in tags)

    async def get_user(self, user_id: str) -> dict | None:
        """
        GET /api/v1/users/{user_id}
        Returns full user record including email, or None on 404.
        """
        return await self._get_or_none(f"/api/v1/users/{user_id}")

    async def search_assets(
        self,
        query: str,
        entity_type: str | None = None,
    ) -> list[dict]:
        """
        GET /api/v1/search/query?q={query}&index={entity_type}_search_index
        Returns matching assets. Pass entity_type=None to search all indexes.
        """
        index = f"{entity_type}_search_index" if entity_type else "all"
        params: dict[str, Any] = {"q": query, "index": index, "size": 20}
        try:
            data = await self._get("/api/v1/search/query", params=params)
        except httpx.HTTPStatusError:
            logger.warning("search_assets failed for query=%r index=%s", query, index)
            return []
        hits = (
            data.get("hits", {}).get("hits", [])
            if isinstance(data.get("hits"), dict)
            else []
        )
        results = []
        for hit in hits:
            src = hit.get("_source", {})
            results.append(
                {
                    "id": src.get("id", ""),
                    "name": src.get("name", ""),
                    "fullyQualifiedName": src.get("fullyQualifiedName", ""),
                    "type": src.get("entityType", src.get("type", "")),
                    "description": src.get("description", ""),
                }
            )
        return results
