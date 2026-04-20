"""Seed OpenMetadata with the FoodieExpress demo dataset.

Run:  python scripts/seed_openmetadata.py

Requires: docker, Python 3.11+, deps in scripts/requirements.txt, and a
running OpenMetadata at $OPENMETADATA_HOST with $OPENMETADATA_JWT_TOKEN
set in .env.

The script is idempotent — re-running it skips entities that already exist
and tops up only what is missing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import httpx
from dotenv import load_dotenv
from faker import Faker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

OM_HOST = os.getenv("OPENMETADATA_HOST", "http://localhost:8585").rstrip("/")
OM_TOKEN = (os.getenv("OPENMETADATA_JWT_TOKEN") or "").strip()
OM_API = f"{OM_HOST}/api/v1"

PG_CONTAINER = "foodieexpress-postgres"
PG_IMAGE = "postgres:16-alpine"
PG_PORT = 5433
PG_USER = "postgres"
PG_PASSWORD = "postgres"
PG_DB = "foodieexpress"
ROWS_PER_TABLE = 500

DB_SERVICE = "FoodieExpressPostgres"
DB_NAME = "foodieexpress"
DB_SCHEMA = "public"
SCHEMA_FQN = f"{DB_SERVICE}.{DB_NAME}.{DB_SCHEMA}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")


# ---------------------------------------------------------------------------
# Postgres bootstrap
# ---------------------------------------------------------------------------

DDL: list[str] = [
    """CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        email VARCHAR(320) NOT NULL,
        phone VARCHAR(32),
        full_name VARCHAR(120),
        created_at TIMESTAMP,
        city VARCHAR(80)
    )""",
    """CREATE TABLE IF NOT EXISTS restaurants (
        id UUID PRIMARY KEY,
        name VARCHAR(160) NOT NULL,
        cuisine VARCHAR(60),
        city VARCHAR(80),
        rating DECIMAL(2,1),
        owner_contact VARCHAR(32)
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        id UUID PRIMARY KEY,
        user_id UUID REFERENCES users(id),
        restaurant_id UUID REFERENCES restaurants(id),
        amount_cents INT,
        status VARCHAR(32),
        created_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS deliveries (
        id UUID PRIMARY KEY,
        order_id UUID REFERENCES orders(id),
        driver_phone VARCHAR(32),
        delivered_at TIMESTAMP,
        status VARCHAR(32)
    )""",
    """CREATE TABLE IF NOT EXISTS payments (
        id UUID PRIMARY KEY,
        order_id UUID REFERENCES orders(id),
        card_last_4 VARCHAR(4),
        amount_cents INT,
        status VARCHAR(32)
    )""",
]

INDIAN_CITIES = [
    "Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Pune", "Chennai",
    "Kolkata", "Gurugram", "Noida", "Jaipur", "Ahmedabad", "Lucknow",
]
CUISINES = [
    "North Indian", "South Indian", "Mughlai", "Chinese", "Italian",
    "Continental", "Thai", "Mexican", "Bengali", "Punjabi", "Street Food",
]


def ensure_postgres_container() -> None:
    """docker run -d Postgres on a side port if not already up."""
    log.info("[postgres] ensuring container '%s' is running", PG_CONTAINER)
    status = subprocess.run(
        [
            "docker", "ps", "-a",
            "--filter", f"name=^{PG_CONTAINER}$",
            "--format", "{{.Status}}",
        ],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    if not status:
        log.info("[postgres] no container yet → creating")
        subprocess.run(
            [
                "docker", "run", "-d", "--name", PG_CONTAINER,
                "-e", f"POSTGRES_USER={PG_USER}",
                "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
                "-e", f"POSTGRES_DB={PG_DB}",
                "-p", f"{PG_PORT}:5432",
                PG_IMAGE,
            ],
            check=True, capture_output=True,
        )
    elif status.startswith("Up"):
        log.info("[postgres] already running")
    else:
        log.info("[postgres] exists but stopped → starting")
        subprocess.run(["docker", "start", PG_CONTAINER], check=True, capture_output=True)


async def wait_for_postgres(timeout_s: int = 60) -> None:
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_err: Exception | None = None
    while asyncio.get_event_loop().time() < deadline:
        try:
            conn = await asyncpg.connect(
                host="localhost", port=PG_PORT,
                user=PG_USER, password=PG_PASSWORD, database=PG_DB,
            )
            await conn.close()
            log.info("[postgres] accepting connections on :%d", PG_PORT)
            return
        except Exception as exc:
            last_err = exc
            await asyncio.sleep(1.0)
    raise RuntimeError(f"postgres not ready in {timeout_s}s: {last_err}")


async def seed_postgres_rows() -> None:
    fake = Faker("en_IN")
    Faker.seed(42)
    conn = await asyncpg.connect(
        host="localhost", port=PG_PORT,
        user=PG_USER, password=PG_PASSWORD, database=PG_DB,
    )
    try:
        for stmt in DDL:
            await conn.execute(stmt)

        existing = await conn.fetchval("SELECT count(*) FROM users")
        if existing and existing >= ROWS_PER_TABLE:
            log.info("[postgres] tables already seeded (%d users) → skipping", existing)
            return

        log.info("[postgres] seeding ~%d rows per table", ROWS_PER_TABLE)
        users: list[tuple] = []
        for _ in range(ROWS_PER_TABLE):
            users.append((
                uuid.uuid4(),
                fake.unique.email(),
                fake.phone_number(),
                fake.name(),
                fake.date_time_between("-2y", "now"),
                fake.random_element(INDIAN_CITIES),
            ))
        await conn.executemany(
            "INSERT INTO users(id,email,phone,full_name,created_at,city) "
            "VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
            users,
        )
        user_ids = [u[0] for u in users]

        restaurants: list[tuple] = []
        for _ in range(ROWS_PER_TABLE):
            restaurants.append((
                uuid.uuid4(),
                f"{fake.company()} {fake.random_element(['Kitchen','Bistro','Eatery','House','Dhaba'])}",
                fake.random_element(CUISINES),
                fake.random_element(INDIAN_CITIES),
                round(fake.pyfloat(min_value=2.5, max_value=5.0, right_digits=1), 1),
                fake.phone_number(),
            ))
        await conn.executemany(
            "INSERT INTO restaurants(id,name,cuisine,city,rating,owner_contact) "
            "VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
            restaurants,
        )
        restaurant_ids = [r[0] for r in restaurants]

        orders: list[tuple] = []
        statuses = ["delivered", "delivered", "delivered", "delivered", "cancelled", "in_progress"]
        for _ in range(ROWS_PER_TABLE):
            orders.append((
                uuid.uuid4(),
                fake.random_element(user_ids),
                fake.random_element(restaurant_ids),
                fake.random_int(15_000, 250_000),
                fake.random_element(statuses),
                fake.date_time_between("-90d", "now"),
            ))
        await conn.executemany(
            "INSERT INTO orders(id,user_id,restaurant_id,amount_cents,status,created_at) "
            "VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
            orders,
        )

        deliveries: list[tuple] = []
        for o in orders:
            delivered = o[4] == "delivered"
            deliveries.append((
                uuid.uuid4(),
                o[0],
                fake.phone_number(),
                fake.date_time_between(start_date=o[5], end_date="now") if delivered else None,
                "delivered" if delivered else o[4],
            ))
        await conn.executemany(
            "INSERT INTO deliveries(id,order_id,driver_phone,delivered_at,status) "
            "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
            deliveries,
        )

        payments: list[tuple] = []
        for o in orders:
            payments.append((
                uuid.uuid4(),
                o[0],
                f"{fake.random_int(1000, 9999)}",
                o[3],
                "captured" if o[4] == "delivered" else "pending",
            ))
        await conn.executemany(
            "INSERT INTO payments(id,order_id,card_last_4,amount_cents,status) "
            "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
            payments,
        )
        log.info(
            "[postgres] seeded users=%d restaurants=%d orders=%d deliveries=%d payments=%d",
            len(users), len(restaurants), len(orders), len(deliveries), len(payments),
        )
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# OpenMetadata client
# ---------------------------------------------------------------------------


class OMClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def __aenter__(self) -> "OMClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.client.aclose()

    async def get(self, path: str, params: dict | None = None) -> dict | None:
        r = await self.client.get(path, params=params)
        if r.status_code == 404:
            return None
        if r.is_error:
            log.warning("GET %s → %d %s", path, r.status_code, r.text[:200])
            return None
        return r.json()

    async def post(self, path: str, payload: dict) -> dict | None:
        r = await self.client.post(path, json=payload)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 409:
            return None
        log.warning("POST %s → %d %s", path, r.status_code, r.text[:300])
        return None

    async def put(self, path: str, payload: dict) -> dict | None:
        r = await self.client.put(path, json=payload)
        if r.status_code in (200, 201):
            return r.json()
        log.warning("PUT %s → %d %s", path, r.status_code, r.text[:300])
        return None

    async def patch(self, path: str, ops: list[dict]) -> dict | None:
        r = await self.client.patch(
            path,
            content=json.dumps(ops),
            headers={"Content-Type": "application/json-patch+json"},
        )
        if r.status_code in (200, 201):
            return r.json()
        log.warning("PATCH %s → %d %s", path, r.status_code, r.text[:300])
        return None

    async def upsert(self, collection: str, fqn_lookup: str, payload: dict) -> dict | None:
        """GET by FQN; if missing, POST."""
        found = await self.get(fqn_lookup)
        if found:
            return found
        created = await self.post(collection, payload)
        if created is None:
            # Race / 409 — re-fetch
            return await self.get(fqn_lookup)
        return created


# ---------------------------------------------------------------------------
# Entity definitions
# ---------------------------------------------------------------------------

TABLE_COLUMNS: dict[str, list[dict]] = {
    "users": [
        {"name": "id", "dataType": "UUID", "constraint": "PRIMARY_KEY"},
        {"name": "email", "dataType": "VARCHAR", "dataLength": 320},
        {"name": "phone", "dataType": "VARCHAR", "dataLength": 32},
        {"name": "full_name", "dataType": "VARCHAR", "dataLength": 120},
        {"name": "created_at", "dataType": "TIMESTAMP"},
        {"name": "city", "dataType": "VARCHAR", "dataLength": 80},
    ],
    "restaurants": [
        {"name": "id", "dataType": "UUID", "constraint": "PRIMARY_KEY"},
        {"name": "name", "dataType": "VARCHAR", "dataLength": 160},
        {"name": "cuisine", "dataType": "VARCHAR", "dataLength": 60},
        {"name": "city", "dataType": "VARCHAR", "dataLength": 80},
        {"name": "rating", "dataType": "DECIMAL", "precision": 2, "scale": 1},
        {"name": "owner_contact", "dataType": "VARCHAR", "dataLength": 32},
    ],
    "orders": [
        {"name": "id", "dataType": "UUID", "constraint": "PRIMARY_KEY"},
        {"name": "user_id", "dataType": "UUID"},
        {"name": "restaurant_id", "dataType": "UUID"},
        {"name": "amount_cents", "dataType": "INT"},
        {"name": "status", "dataType": "VARCHAR", "dataLength": 32},
        {"name": "created_at", "dataType": "TIMESTAMP"},
    ],
    "deliveries": [
        {"name": "id", "dataType": "UUID", "constraint": "PRIMARY_KEY"},
        {"name": "order_id", "dataType": "UUID"},
        {"name": "driver_phone", "dataType": "VARCHAR", "dataLength": 32},
        {"name": "delivered_at", "dataType": "TIMESTAMP"},
        {"name": "status", "dataType": "VARCHAR", "dataLength": 32},
    ],
    "payments": [
        {"name": "id", "dataType": "UUID", "constraint": "PRIMARY_KEY"},
        {"name": "order_id", "dataType": "UUID"},
        {"name": "card_last_4", "dataType": "VARCHAR", "dataLength": 4},
        {"name": "amount_cents", "dataType": "INT"},
        {"name": "status", "dataType": "VARCHAR", "dataLength": 32},
    ],
}

DASHBOARDS = [
    ("Looker", "cfo_weekly_revenue", "CFO Weekly Revenue"),
    ("Metabase", "support_agent_console", "Support Agent Console"),
    ("Tableau", "marketing_regional_cohorts", "Marketing Regional Cohorts"),
    ("Superset", "fraud_alerts_live", "Fraud Alerts Live"),
]
ML_MODELS = [
    ("churn_predictor_v2", "Churn Predictor v2", "Random Forest"),
    ("fraud_detection_v4", "Fraud Detection v4", "Gradient Boosted Trees"),
]
PIPELINES = [
    ("Airflow", "daily_revenue_etl", "Daily Revenue ETL"),
    ("dbt", "customer_enrichment_etl", "Customer Enrichment ETL"),
]
USERS = [
    ("priya", "Priya Sharma", "priya@foodieexpress.com"),
    ("arjun", "Arjun Verma", "arjun@foodieexpress.com"),
    ("kavya", "Kavya Iyer", "kavya@foodieexpress.com"),
    ("raj", "Raj Khanna", "raj@foodieexpress.com"),
]


# ---------------------------------------------------------------------------
# Service / database / schema / table creation
# ---------------------------------------------------------------------------


async def ensure_db_service(om: OMClient) -> dict | None:
    fqn = DB_SERVICE
    payload = {
        "name": DB_SERVICE,
        "serviceType": "Postgres",
        "description": "FoodieExpress production OLTP database (demo).",
        "connection": {
            "config": {
                "type": "Postgres",
                "username": PG_USER,
                "authType": {"password": PG_PASSWORD},
                "hostPort": f"host.docker.internal:{PG_PORT}",
                "database": PG_DB,
            }
        },
    }
    return await om.upsert(
        "/services/databaseServices",
        f"/services/databaseServices/name/{fqn}",
        payload,
    )


async def ensure_database(om: OMClient) -> dict | None:
    fqn = f"{DB_SERVICE}.{DB_NAME}"
    return await om.upsert(
        "/databases",
        f"/databases/name/{fqn}",
        {"name": DB_NAME, "service": DB_SERVICE},
    )


async def ensure_schema(om: OMClient) -> dict | None:
    return await om.upsert(
        "/databaseSchemas",
        f"/databaseSchemas/name/{SCHEMA_FQN}",
        {"name": DB_SCHEMA, "database": f"{DB_SERVICE}.{DB_NAME}"},
    )


async def ensure_tables(om: OMClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for table_name, columns in TABLE_COLUMNS.items():
        fqn = f"{SCHEMA_FQN}.{table_name}"
        entity = await om.upsert(
            "/tables",
            f"/tables/name/{fqn}?fields=columns,tags,owners,owner",
            {
                "name": table_name,
                "databaseSchema": SCHEMA_FQN,
                "columns": columns,
            },
        )
        if entity:
            out[table_name] = entity
            log.info("[tables] %s ✓", fqn)
    return out


# ---------------------------------------------------------------------------
# Custom dashboard / mlmodel / pipeline services
# ---------------------------------------------------------------------------


async def _ensure_custom_service(
    om: OMClient,
    collection: str,
    name: str,
    custom_type: str,
) -> dict | None:
    payload = {
        "name": name,
        "serviceType": custom_type,
        "connection": {"config": {"type": custom_type}},
    }
    return await om.upsert(
        f"/services/{collection}",
        f"/services/{collection}/name/{name}",
        payload,
    )


async def ensure_dashboards(om: OMClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for service_name, name, display in DASHBOARDS:
        await _ensure_custom_service(om, "dashboardServices", service_name, "CustomDashboard")
        fqn = f"{service_name}.{name}"
        entity = await om.upsert(
            "/dashboards",
            f"/dashboards/name/{fqn}?fields=owners,owner",
            {
                "name": name,
                "displayName": display,
                "service": service_name,
                "sourceUrl": f"https://demo.foodieexpress.in/dashboards/{name}",
            },
        )
        if entity:
            out[name] = entity
            log.info("[dashboards] %s ✓", fqn)
    return out


async def ensure_mlmodels(om: OMClient) -> dict[str, dict]:
    service_name = "InternalML"
    await _ensure_custom_service(om, "mlmodelServices", service_name, "CustomMlModel")
    out: dict[str, dict] = {}
    for name, display, algorithm in ML_MODELS:
        fqn = f"{service_name}.{name}"
        entity = await om.upsert(
            "/mlmodels",
            f"/mlmodels/name/{fqn}?fields=owners,owner",
            {
                "name": name,
                "displayName": display,
                "service": service_name,
                "algorithm": algorithm,
            },
        )
        if entity:
            out[name] = entity
            log.info("[mlmodels] %s ✓", fqn)
    return out


async def ensure_pipelines(om: OMClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for service_name, name, display in PIPELINES:
        await _ensure_custom_service(om, "pipelineServices", service_name, "CustomPipeline")
        fqn = f"{service_name}.{name}"
        entity = await om.upsert(
            "/pipelines",
            f"/pipelines/name/{fqn}?fields=owners,owner",
            {
                "name": name,
                "displayName": display,
                "service": service_name,
            },
        )
        if entity:
            out[name] = entity
            log.info("[pipelines] %s ✓", fqn)
    return out


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def ensure_users(om: OMClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, display, email in USERS:
        entity = await om.upsert(
            "/users",
            f"/users/name/{name}",
            {"name": name, "displayName": display, "email": email},
        )
        if entity:
            out[name] = entity
            log.info("[users] %s ✓", name)
    return out


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def _owner_ref(user: dict) -> dict:
    return {"id": user["id"], "type": "user"}


async def assign_owner(
    om: OMClient,
    entity_endpoint: str,
    entity: dict,
    user: dict,
) -> None:
    """Set owner on an entity, supporting both pre-1.5 (`owner`) and post-1.5 (`owners`)."""
    eid = entity["id"]
    has_owners = "owners" in entity
    has_singular = "owner" in entity

    # Try plural first (current API).
    if has_owners or not has_singular:
        ops = [{"op": "add", "path": "/owners", "value": [_owner_ref(user)]}]
        if await om.patch(f"{entity_endpoint}/{eid}", ops):
            return

    # Fall back to singular `owner` field.
    ops_legacy = [{"op": "add", "path": "/owner", "value": _owner_ref(user)}]
    await om.patch(f"{entity_endpoint}/{eid}", ops_legacy)


async def assign_all_owners(
    om: OMClient,
    tables: dict[str, dict],
    dashboards: dict[str, dict],
    mlmodels: dict[str, dict],
    pipelines: dict[str, dict],
    users: dict[str, dict],
) -> None:
    plan: list[tuple[str, dict, dict]] = []
    if "priya" in users:
        if "cfo_weekly_revenue" in dashboards:
            plan.append(("/dashboards", dashboards["cfo_weekly_revenue"], users["priya"]))
        if "daily_revenue_etl" in pipelines:
            plan.append(("/pipelines", pipelines["daily_revenue_etl"], users["priya"]))
    if "arjun" in users:
        for m in ("churn_predictor_v2", "fraud_detection_v4"):
            if m in mlmodels:
                plan.append(("/mlmodels", mlmodels[m], users["arjun"]))
    if "kavya" in users:
        for d in ("support_agent_console", "fraud_alerts_live"):
            if d in dashboards:
                plan.append(("/dashboards", dashboards[d], users["kavya"]))
    if "raj" in users:
        for t in ("users", "orders"):
            if t in tables:
                plan.append(("/tables", tables[t], users["raj"]))

    for endpoint, entity, user in plan:
        await assign_owner(om, endpoint, entity, user)
        log.info("[owners] %s → %s", entity.get("fullyQualifiedName", entity["name"]), user["name"])


# ---------------------------------------------------------------------------
# Classification + tags
# ---------------------------------------------------------------------------

PII_TAGS = [
    ("Email", "Email address — direct identifier."),
    ("Phone", "Phone number — direct identifier."),
    ("Financial", "Financial data — payment information."),
]

# (table, column, tag suffix)
COLUMN_TAGS: list[tuple[str, str, str]] = [
    ("users", "email", "Email"),
    ("users", "phone", "Phone"),
    ("deliveries", "driver_phone", "Phone"),
    ("restaurants", "owner_contact", "Phone"),
    ("payments", "card_last_4", "Financial"),
    ("orders", "amount_cents", "Financial"),
]


async def ensure_classification_and_tags(om: OMClient) -> None:
    await om.upsert(
        "/classifications",
        "/classifications/name/PII",
        {"name": "PII", "description": "Personally Identifiable Information."},
    )
    for tag_name, desc in PII_TAGS:
        fqn = f"PII.{tag_name}"
        await om.upsert(
            "/tags",
            f"/tags/name/{fqn}",
            {"classification": "PII", "name": tag_name, "description": desc},
        )
        log.info("[tags] %s ✓", fqn)


async def apply_column_tags(om: OMClient, tables: dict[str, dict]) -> None:
    # Refresh tables with columns + tags so PATCH path indices line up.
    for table_name in {t for t, _, _ in COLUMN_TAGS}:
        if table_name not in tables:
            continue
        fqn = f"{SCHEMA_FQN}.{table_name}"
        fresh = await om.get(f"/tables/name/{fqn}?fields=columns,tags")
        if not fresh:
            continue
        columns = fresh.get("columns", [])
        col_index = {c["name"]: i for i, c in enumerate(columns)}

        ops: list[dict] = []
        for t, col, suffix in COLUMN_TAGS:
            if t != table_name or col not in col_index:
                continue
            tag_label = {
                "tagFQN": f"PII.{suffix}",
                "source": "Classification",
                "labelType": "Manual",
                "state": "Confirmed",
            }
            existing = columns[col_index[col]].get("tags") or []
            already = any(x.get("tagFQN") == tag_label["tagFQN"] for x in existing)
            if already:
                continue
            ops.append({
                "op": "add",
                "path": f"/columns/{col_index[col]}/tags",
                "value": existing + [tag_label],
            })
        if ops:
            await om.patch(f"/tables/{fresh['id']}", ops)
            log.info("[tags] applied %d column tag(s) on %s", len(ops), table_name)


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


@dataclass
class LineageEdge:
    src_kind: str           # 'table' | 'pipeline' | 'mlmodel' | 'dashboard'
    src_name: str
    dst_kind: str
    dst_name: str
    columns: list[str] = field(default_factory=list)  # source column names (for table sources)


# Each upstream→downstream edge. Pipelines fan out through two edges
# (table → pipeline, pipeline → dashboard/mlmodel).
LINEAGE: list[LineageEdge] = [
    LineageEdge("table", "users", "dashboard", "marketing_regional_cohorts", ["email"]),
    LineageEdge("table", "users", "mlmodel",  "churn_predictor_v2",         ["email"]),

    LineageEdge("table", "users",      "pipeline",  "daily_revenue_etl",  ["email"]),
    LineageEdge("table", "orders",     "pipeline",  "daily_revenue_etl",  ["amount_cents"]),
    LineageEdge("pipeline", "daily_revenue_etl", "dashboard", "cfo_weekly_revenue"),

    LineageEdge("table", "users", "dashboard", "support_agent_console", ["phone"]),
    LineageEdge("table", "deliveries", "dashboard", "support_agent_console", ["driver_phone"]),

    LineageEdge("table", "users", "pipeline", "customer_enrichment_etl", ["phone"]),
    LineageEdge("pipeline", "customer_enrichment_etl", "mlmodel", "fraud_detection_v4"),

    LineageEdge("table", "orders",   "mlmodel", "fraud_detection_v4", ["amount_cents"]),
    LineageEdge("table", "payments", "mlmodel", "fraud_detection_v4", ["card_last_4"]),
]


def _ref(kind: str, name: str, lookups: dict[str, dict[str, dict]]) -> dict | None:
    bucket = lookups.get(kind, {})
    entity = bucket.get(name)
    if not entity:
        log.warning("[lineage] missing %s '%s'", kind, name)
        return None
    return {"id": entity["id"], "type": kind}


async def ensure_lineage(
    om: OMClient,
    tables: dict[str, dict],
    dashboards: dict[str, dict],
    mlmodels: dict[str, dict],
    pipelines: dict[str, dict],
) -> int:
    lookups = {
        "table": tables,
        "dashboard": dashboards,
        "mlmodel": mlmodels,
        "pipeline": pipelines,
    }

    created = 0
    for edge in LINEAGE:
        src = _ref(edge.src_kind, edge.src_name, lookups)
        dst = _ref(edge.dst_kind, edge.dst_name, lookups)
        if not src or not dst:
            continue

        payload: dict[str, Any] = {"edge": {"fromEntity": src, "toEntity": dst}}
        if edge.columns and edge.src_kind == "table":
            src_fqn = f"{SCHEMA_FQN}.{edge.src_name}"
            payload["edge"]["lineageDetails"] = {
                "columnsLineage": [
                    {"fromColumns": [f"{src_fqn}.{c}"]} for c in edge.columns
                ],
            }
        if await om.put("/lineage", payload):
            created += 1
            tag = ",".join(edge.columns) if edge.columns else "—"
            log.info("[lineage] %s.%s → %s.%s (%s)",
                     edge.src_kind, edge.src_name,
                     edge.dst_kind, edge.dst_name, tag)
    return created


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run() -> None:
    if not OM_TOKEN:
        log.error("OPENMETADATA_JWT_TOKEN is not set in .env — aborting")
        sys.exit(1)

    ensure_postgres_container()
    await wait_for_postgres()
    await seed_postgres_rows()

    async with OMClient(OM_API, OM_TOKEN) as om:
        # Probe auth early
        probe = await om.get("/system/version")
        if probe is None:
            log.warning("could not reach %s/system/version — continuing anyway", OM_API)

        await ensure_db_service(om)
        await ensure_database(om)
        await ensure_schema(om)
        tables = await ensure_tables(om)

        dashboards, mlmodels, pipelines, users = await asyncio.gather(
            ensure_dashboards(om),
            ensure_mlmodels(om),
            ensure_pipelines(om),
            ensure_users(om),
        )

        await ensure_classification_and_tags(om)
        await apply_column_tags(om, tables)
        await assign_all_owners(om, tables, dashboards, mlmodels, pipelines, users)
        edges = await ensure_lineage(om, tables, dashboards, mlmodels, pipelines)

        print()
        print("─" * 60)
        print("  FoodieExpress demo dataset seeded")
        print("─" * 60)
        print(f"  tables       : {len(tables)}")
        print(f"  dashboards   : {len(dashboards)}")
        print(f"  ml models    : {len(mlmodels)}")
        print(f"  pipelines    : {len(pipelines)}")
        print(f"  users        : {len(users)}")
        print(f"  lineage edges: {edges}")
        print(f"  → explore at  {OM_HOST}")
        print("─" * 60)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("interrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
