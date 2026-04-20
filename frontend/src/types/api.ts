export type Severity = "safe" | "warning" | "breaking";

export type ColumnRef = {
  table: string;
  column: string;
};

export type Owner = {
  id: string;
  name: string;
  role: string;
};

export type AnalysisCard = {
  id: string;
  prNumber: number;
  repo: string;
  title: string;
  severity: Severity;
  columnsAffected: ColumnRef[];
  downstreamCount: number;
  downstreamSummary: string;
  owners: Owner[];
  author: string;
  createdAt: string;
};

export type GovernancePulse = {
  untagged_pii: number;
  assets_no_owner: number;
  orphaned_nodes: number;
};

export type LineageNode = {
  id: string;
  label: string;
  type: "table" | "dashboard" | "mlmodel" | "pipeline";
};

export type LineageEdge = {
  from: string;
  to: string;
};

export type LineageGraph = {
  fqn: string;
  nodes: LineageNode[];
  edges: LineageEdge[];
};

export type BackendSeverity = "critical" | "high" | "medium" | "low";

export type SchemaChange = {
  change_type: string;
  table: string;
  database: string | null;
  old_column: string | null;
  new_column: string | null;
  old_type: string | null;
  new_type: string | null;
  risk: BackendSeverity;
  raw_sql: string;
  line_number: number;
};

export type AffectedAsset = {
  id: string;
  name: string;
  fqn: string;
  asset_type: string;
  owner_name: string | null;
  owner_email: string | null;
  slack_handle: string | null;
  severity: BackendSeverity;
  reason: string;
};

export type BlastRadiusReport = {
  schema_change: SchemaChange;
  affected_assets: AffectedAsset[];
  affected_columns: string[];
  pii_involved: boolean;
  pii_classifications: string[];
  overall_severity: BackendSeverity;
  requires_governance_approval: boolean;
  total_owners_to_notify: number;
  unique_owner_emails: string[];
  summary_one_line: string;
  analysis_timestamp: string;
};
