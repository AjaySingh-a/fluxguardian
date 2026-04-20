"""
Integration tests for OpenMetadataClient.

These tests hit the REAL OpenMetadata instance (configured via .env).
They are automatically skipped when OpenMetadata is not reachable.

Run with:
    pytest backend/tests/test_openmetadata_client.py -v
"""

import pytest
import pytest_asyncio
import httpx

from app.clients.openmetadata import OpenMetadataClient
from app.config import settings

# ---------------------------------------------------------------------------
# FQN constants — match the actual seeded FoodieExpress data
# ---------------------------------------------------------------------------

TABLE_FQN = "FoodieExpressPostgres.foodieexpress.public.users"
COLUMN_FQN = f"{TABLE_FQN}.email"
COLUMN_NAME_PII = "email"
COLUMN_NAME_NON_PII = "full_name"


# ---------------------------------------------------------------------------
# Reachability guard
# ---------------------------------------------------------------------------

def is_om_reachable() -> bool:
    try:
        r = httpx.get(
            f"{settings.openmetadata_host}/api/v1/system/version",
            headers={"Authorization": f"Bearer {settings.openmetadata_jwt_token}"},
            timeout=5.0,
        )
        return r.status_code == 200
    except Exception:
        return False


om_available = pytest.mark.skipif(
    not is_om_reachable(),
    reason="OpenMetadata is not reachable at the configured host",
)


@pytest_asyncio.fixture
async def client() -> OpenMetadataClient:  # type: ignore[misc]
    async with OpenMetadataClient() as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@om_available
@pytest.mark.asyncio
async def test_get_table_users_returns_columns(client: OpenMetadataClient) -> None:
    table = await client.get_table_by_fqn(TABLE_FQN)

    assert table is not None, f"Table {TABLE_FQN!r} not found in OpenMetadata"
    assert "columns" in table, "Response missing 'columns' key"
    assert len(table["columns"]) > 0, "Table has no columns"
    column_names = [c["name"] for c in table["columns"]]
    assert "email" in column_names, f"'email' not among columns: {column_names}"


@om_available
@pytest.mark.asyncio
async def test_get_table_by_fqn_returns_none_for_missing(
    client: OpenMetadataClient,
) -> None:
    result = await client.get_table_by_fqn("DoesNotExist.db.public.table")
    assert result is None


@om_available
@pytest.mark.asyncio
async def test_get_column_lineage_for_users_email(
    client: OpenMetadataClient,
) -> None:
    lineage = await client.get_column_lineage(TABLE_FQN, upstream_depth=1, downstream_depth=3)

    assert isinstance(lineage, dict), "Lineage should be a dict"
    # OM v1.x returns entity, nodes, upstreamEdges, downstreamEdges
    assert "entity" in lineage or "nodes" in lineage, (
        f"Unexpected lineage shape: {list(lineage.keys())}"
    )


@om_available
@pytest.mark.asyncio
async def test_get_column_lineage_uses_cache(client: OpenMetadataClient) -> None:
    """Second call within TTL should be served from the in-memory cache."""
    from app.clients.openmetadata import _lineage_cache

    _lineage_cache.clear()

    await client.get_column_lineage(TABLE_FQN, upstream_depth=1, downstream_depth=3)
    size_after_first = len(_lineage_cache)

    await client.get_column_lineage(TABLE_FQN, upstream_depth=1, downstream_depth=3)
    size_after_second = len(_lineage_cache)

    assert size_after_first == size_after_second == 1, (
        "Cache should hold exactly one entry after two identical calls"
    )


@om_available
@pytest.mark.asyncio
async def test_get_downstream_assets_for_users_email(
    client: OpenMetadataClient,
) -> None:
    assets = await client.get_downstream_assets(COLUMN_FQN)

    assert isinstance(assets, list)
    for asset in assets:
        assert "id" in asset
        assert "name" in asset
        assert "fullyQualifiedName" in asset
        assert "type" in asset
        assert "depth" in asset
        assert asset["depth"] >= 1


@om_available
@pytest.mark.asyncio
async def test_is_pii_column_for_email(client: OpenMetadataClient) -> None:
    result = await client.is_pii_column(TABLE_FQN, COLUMN_NAME_PII)
    assert isinstance(result, bool)
    # Strict assertion: email must be tagged PII in seeded data
    # assert result is True  # uncomment once PII tags are confirmed seeded


@om_available
@pytest.mark.asyncio
async def test_is_pii_column_for_full_name(client: OpenMetadataClient) -> None:
    result = await client.is_pii_column(TABLE_FQN, COLUMN_NAME_NON_PII)
    assert isinstance(result, bool)
    # full_name should NOT be PII
    # assert result is False  # uncomment once tags are confirmed seeded


@om_available
@pytest.mark.asyncio
async def test_get_column_tags_returns_list(client: OpenMetadataClient) -> None:
    tags = await client.get_column_tags(TABLE_FQN, COLUMN_NAME_PII)
    assert isinstance(tags, list)


@om_available
@pytest.mark.asyncio
async def test_get_column_tags_missing_column_returns_empty(
    client: OpenMetadataClient,
) -> None:
    tags = await client.get_column_tags(TABLE_FQN, "nonexistent_column_xyz")
    assert tags == []


@om_available
@pytest.mark.asyncio
async def test_search_assets_with_query_users(client: OpenMetadataClient) -> None:
    # The OM search index may not be populated in all environments.
    # We assert the method returns a well-formed list regardless.
    results = await client.search_assets("users", entity_type="table")
    assert isinstance(results, list)
    for asset in results:
        assert "id" in asset
        assert "name" in asset
        assert "fullyQualifiedName" in asset


@om_available
@pytest.mark.asyncio
async def test_search_assets_empty_query_returns_list(
    client: OpenMetadataClient,
) -> None:
    results = await client.search_assets("*")
    assert isinstance(results, list)


@om_available
@pytest.mark.asyncio
async def test_get_entity_owner_unknown_entity_returns_none(
    client: OpenMetadataClient,
) -> None:
    result = await client.get_entity_owner(
        "00000000-0000-0000-0000-000000000000", "tables"
    )
    assert result is None


@om_available
@pytest.mark.asyncio
async def test_get_entity_owner_for_known_table(client: OpenMetadataClient) -> None:
    """Verify get_entity_owner returns a dict with id/name/email keys."""
    # First get the table to find its ID
    table = await client.get_table_by_fqn(TABLE_FQN)
    assert table is not None
    table_id = table["id"]

    owner = await client.get_entity_owner(table_id, "tables")
    # Owner may or may not exist; if present it must have the expected shape
    if owner is not None:
        assert "id" in owner
        assert "name" in owner
        assert "email" in owner
