"""
blast_radius.py — Core analysis engine.

Given a SchemaChange, queries OpenMetadata to discover all downstream assets
that depend on the changed column/table, checks for PII involvement, derives
owner contacts, and returns a structured BlastRadiusReport.
"""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import BaseModel

from app.clients.openmetadata import OpenMetadataClient
from app.parsers.schema_diff import SchemaChange

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Severity = Literal["critical", "high", "medium", "low"]
AssetType = Literal["dashboard", "mlmodel", "pipeline", "table"]

_SEVERITY_ORDER: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# OM entity type → REST plural for API calls
_ENTITY_PLURAL: dict[str, str] = {
    "table": "tables",
    "dashboard": "dashboards",
    "pipeline": "pipelines",
    "mlmodel": "mlmodels",
    "chart": "charts",
    "topic": "topics",
}

_GOVERNANCE_CHANGE_TYPES = {"drop_column", "drop_table", "rename_column"}


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------


class AffectedAsset(BaseModel):
    id: str
    name: str
    fqn: str
    asset_type: str  # dashboard | mlmodel | pipeline | table
    owner_name: str | None
    owner_email: str | None
    slack_handle: str | None
    severity: Severity
    reason: str


class BlastRadiusReport(BaseModel):
    schema_change: SchemaChange
    affected_assets: list[AffectedAsset]
    affected_columns: list[str]
    pii_involved: bool
    pii_classifications: list[str]
    overall_severity: Severity
    requires_governance_approval: bool
    total_owners_to_notify: int
    unique_owner_emails: list[str]
    summary_one_line: str
    analysis_timestamp: datetime


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

def _max_severity(*severities: Severity) -> Severity:
    if not severities:
        return "low"
    return max(severities, key=lambda s: _SEVERITY_ORDER[s])


def _asset_severity(change_type: str, depth: int) -> Severity:
    if change_type in ("drop_column", "drop_table"):
        return "critical"
    if change_type in ("rename_column", "rename_table"):
        return "high" if depth == 1 else "medium"
    if change_type == "alter_column_type":
        return "medium"
    return "low"


def _slack_handle(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return "@" + email.split("@")[0]


def _change_verb(change_type: str) -> str:
    verbs = {
        "rename_column": "Renaming",
        "drop_column": "Dropping",
        "drop_table": "Dropping table",
        "alter_column_type": "Altering type of",
        "add_column": "Adding",
        "rename_table": "Renaming table",
    }
    return verbs.get(change_type, change_type.replace("_", " ").capitalize())


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BlastRadiusEngine:
    """
    Analyses a SchemaChange against live OpenMetadata lineage data and
    returns a BlastRadiusReport describing every downstream impact.
    """

    def __init__(self, om_client: OpenMetadataClient) -> None:
        self.om = om_client

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def analyze(
        self,
        change: SchemaChange,
        om_service: str = "FoodieExpressPostgres",
        om_database: str = "foodieexpress",
        om_schema: str = "public",
    ) -> BlastRadiusReport:
        """
        Full analysis pipeline:
          1. Build affected column FQNs from the SchemaChange
          2. Walk lineage to collect downstream assets
          3. Enrich each asset with owner contact info
          4. Check PII status for affected columns
          5. Compute severity, governance flag, summary
        """
        fqn_prefix = f"{om_service}.{om_database}.{om_schema}"
        table_fqn = f"{fqn_prefix}.{change.table}"

        logger.info(
            "BlastRadius: analysing %s on %s (table FQN: %s)",
            change.change_type, change.table, table_fqn,
        )

        # Step 1 — Determine which column FQNs are directly affected
        affected_col_fqns = await self._build_affected_column_fqns(change, table_fqn)
        logger.info("Affected column FQNs: %s", affected_col_fqns)

        # Step 2 — Walk lineage and collect unique downstream assets
        downstream_map: dict[str, dict] = {}  # id → raw asset dict
        for col_fqn in affected_col_fqns:
            assets = await self._downstream_for_column(col_fqn, table_fqn)
            for a in assets:
                if a["id"] not in downstream_map:
                    downstream_map[a["id"]] = a

        logger.info("Found %d unique downstream assets", len(downstream_map))

        # Step 3 — Enrich assets and build AffectedAsset objects
        affected_assets: list[AffectedAsset] = []
        for raw in downstream_map.values():
            asset = await self._build_affected_asset(raw, change)
            if asset:
                affected_assets.append(asset)

        # Step 4 — PII check on every affected column
        pii_involved, pii_classifications = await self._check_pii(
            change, table_fqn, affected_col_fqns
        )

        # Step 5 — Derive aggregate fields
        overall_severity = self._overall_severity(
            affected_assets, change, pii_involved
        )
        requires_approval = (
            pii_involved and change.change_type in _GOVERNANCE_CHANGE_TYPES
        )

        unique_emails = sorted(
            {a.owner_email for a in affected_assets if a.owner_email}
        )
        summary = self._make_summary(change, affected_assets, pii_involved)

        report = BlastRadiusReport(
            schema_change=change,
            affected_assets=affected_assets,
            affected_columns=affected_col_fqns,
            pii_involved=pii_involved,
            pii_classifications=pii_classifications,
            overall_severity=overall_severity,
            requires_governance_approval=requires_approval,
            total_owners_to_notify=len(unique_emails),
            unique_owner_emails=unique_emails,
            summary_one_line=summary,
            analysis_timestamp=datetime.now(timezone.utc),
        )
        logger.info("BlastRadius complete: %s", summary)
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_affected_column_fqns(
        self, change: SchemaChange, table_fqn: str
    ) -> list[str]:
        """Return the list of column FQNs directly affected by the change."""
        ct = change.change_type

        if ct == "add_column":
            # New column: nothing downstream depends on it yet
            return []

        if ct in ("rename_column", "drop_column", "alter_column_type"):
            col = change.old_column or change.new_column
            if not col:
                logger.warning("Change %s has no column name — skipping FQN", ct)
                return []
            return [f"{table_fqn}.{col}"]

        if ct in ("drop_table", "rename_table"):
            # All existing columns of the table are affected
            return await self._all_column_fqns(table_fqn)

        return []

    async def _all_column_fqns(self, table_fqn: str) -> list[str]:
        """Fetch the table from OM and return every column's FQN."""
        try:
            table = await self.om.get_table_by_fqn(table_fqn)
        except httpx.HTTPStatusError as exc:
            logger.warning("Could not fetch table %s: %s", table_fqn, exc)
            return []
        if not table:
            logger.warning("Table not found in OM: %s", table_fqn)
            return []
        return [
            col.get("fullyQualifiedName", f"{table_fqn}.{col.get('name', '')}")
            for col in table.get("columns", [])
            if col.get("name")
        ]

    async def _downstream_for_column(
        self, col_fqn: str, table_fqn: str
    ) -> list[dict]:
        """
        Walk the lineage graph rooted at the column's parent table and
        return flat list of downstream assets (dicts with id/name/fqn/type/depth).
        """
        try:
            graph = await self.om.get_column_lineage(
                table_fqn, upstream_depth=0, downstream_depth=3, entity_type="table"
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Lineage fetch failed for %s (table %s): %s", col_fqn, table_fqn, exc
            )
            return []

        # Index nodes by id
        nodes: dict[str, dict] = {}
        for node in graph.get("nodes", []):
            nid = node.get("id", "")
            if nid:
                nodes[nid] = node

        root_entity = graph.get("entity", {})
        root_id: str = root_entity.get("id", "")
        if root_id and root_id not in nodes:
            nodes[root_id] = root_entity

        if not root_id:
            logger.warning("No root entity in lineage for %s", table_fqn)
            return []

        # Downstream adjacency from downstreamEdges (ids, not objects)
        adjacency: dict[str, list[str]] = {}
        for edge in graph.get("downstreamEdges", []):
            from_id = edge.get("fromEntity", "")
            to_id = edge.get("toEntity", "")
            if from_id and to_id:
                adjacency.setdefault(from_id, []).append(to_id)

        # BFS — skip the root itself
        visited: set[str] = {root_id}
        queue: deque[tuple[str, int]] = deque([(root_id, 0)])
        results: list[dict] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth > 0:
                node = nodes.get(current_id, {"id": current_id})
                results.append(
                    {
                        "id": current_id,
                        "name": node.get("name", ""),
                        "fqn": node.get("fullyQualifiedName", ""),
                        "type": node.get("type", ""),
                        "depth": depth,
                    }
                )
            for neighbor_id in adjacency.get(current_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

        return results

    async def _enrich_owner(self, entity_id: str, entity_type: str) -> tuple[str, str]:
        """
        Return (owner_name, owner_email) for the given entity.
        Makes two calls: one to get the entity's owners, one to get user email.
        """
        type_plural = _ENTITY_PLURAL.get(entity_type, f"{entity_type}s")
        try:
            owner = await self.om.get_entity_owner(entity_id, type_plural)
        except httpx.HTTPStatusError:
            return "", ""
        if not owner:
            return "", ""

        name = owner.get("name", "")
        email = owner.get("email", "")
        if not email:
            user = await self.om.get_user(owner.get("id", ""))
            if user:
                email = user.get("email", "")
                name = name or user.get("name", "")
        return name, email

    async def _build_affected_asset(
        self, raw: dict, change: SchemaChange
    ) -> AffectedAsset | None:
        depth = raw.get("depth", 1)
        entity_type = raw.get("type", "")
        entity_id = raw.get("id", "")

        if not entity_id:
            return None

        severity = _asset_severity(change.change_type, depth)

        owner_name, owner_email = await self._enrich_owner(entity_id, entity_type)
        slack = _slack_handle(owner_email)

        if depth == 1:
            reason = f"Direct dependency on {change.table} via column-level lineage"
        else:
            reason = f"Indirect dependency (depth {depth}) via transitive lineage from {change.table}"

        return AffectedAsset(
            id=entity_id,
            name=raw.get("name", ""),
            fqn=raw.get("fqn", ""),
            asset_type=entity_type,
            owner_name=owner_name or None,
            owner_email=owner_email or None,
            slack_handle=slack,
            severity=severity,
            reason=reason,
        )

    async def _check_pii(
        self,
        change: SchemaChange,
        table_fqn: str,
        affected_col_fqns: list[str],
    ) -> tuple[bool, list[str]]:
        """
        Check every affected column for PII tags.
        Returns (pii_involved, list_of_pii_tag_fqns).
        """
        if change.change_type == "add_column":
            return False, []

        col_names = [fqn.rsplit(".", 1)[-1] for fqn in affected_col_fqns]
        if not col_names:
            col = change.old_column or change.new_column
            col_names = [col] if col else []

        all_pii_tags: list[str] = []
        for col_name in col_names:
            try:
                tags = await self.om.get_column_tags(table_fqn, col_name)
            except httpx.HTTPStatusError:
                continue
            pii_tags = [t for t in tags if t.upper().startswith("PII")]
            all_pii_tags.extend(pii_tags)

        unique_tags = sorted(set(all_pii_tags))
        return bool(unique_tags), unique_tags

    def _overall_severity(
        self,
        affected_assets: list[AffectedAsset],
        change: SchemaChange,
        pii_involved: bool,
    ) -> Severity:
        if affected_assets:
            return _max_severity(*[a.severity for a in affected_assets])
        if pii_involved:
            return "medium"
        # No downstream assets: severity driven by the change itself
        risk_map: dict[str, Severity] = {
            "drop_column": "critical",
            "drop_table": "critical",
            "rename_column": "high",
            "rename_table": "high",
            "alter_column_type": "medium",
            "add_column": "low",
        }
        return risk_map.get(change.change_type, "low")

    def _make_summary(
        self,
        change: SchemaChange,
        affected_assets: list[AffectedAsset],
        pii_involved: bool,
    ) -> str:
        verb = _change_verb(change.change_type)
        col = change.old_column or change.new_column or ""
        subject = f"{change.table}.{col}" if col else change.table
        n = len(affected_assets)
        asset_str = f"{n} downstream asset{'s' if n != 1 else ''}"
        pii_str = " [PII involved]" if pii_involved else ""
        if n == 0:
            return f"{verb} {subject} has no detected downstream impact{pii_str}"
        return f"{verb} {subject} will impact {asset_str}{pii_str}"
