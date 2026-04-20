export type Severity = "safe" | "breaking" | "warning";

export type Owner = {
  id: string;
  name: string;
  role: string;
};

export type ColumnRef = {
  table: string;
  column: string;
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
  createdAt: string; // ISO
  author: string;
};

export type HeroStat = {
  id: string;
  label: string;
  value: number;
  delta?: number;
  deltaLabel?: string;
  intent?: "default" | "danger";
  format?: "number" | "compact";
};

export type GovernanceStat = {
  id: string;
  label: string;
  value: number;
  hint: string;
};

export const OWNERS: Record<string, Owner> = {
  priya: { id: "priya", name: "Priya Sharma", role: "Finance" },
  arjun: { id: "arjun", name: "Arjun Verma", role: "ML Platform" },
  kavya: { id: "kavya", name: "Kavya Iyer", role: "Compliance" },
  raj:   { id: "raj",   name: "Raj Khanna",  role: "Data Platform" },
};

export const HERO_STATS: HeroStat[] = [
  {
    id: "prs-today",
    label: "PRs Analyzed Today",
    value: 47,
    delta: 18,
    deltaLabel: "vs yesterday",
  },
  {
    id: "breaking-caught",
    label: "Breaking Changes Caught",
    value: 8,
    delta: 33,
    deltaLabel: "this week",
    intent: "danger",
  },
  {
    id: "assets-protected",
    label: "Downstream Assets Protected",
    value: 1284,
    delta: 4,
    deltaLabel: "vs last week",
    format: "compact",
  },
  {
    id: "migration-plans",
    label: "Migration Plans Generated",
    value: 12,
    delta: 50,
    deltaLabel: "this week",
  },
];

export const GOVERNANCE_PULSE: GovernanceStat[] = [
  {
    id: "untagged-pii",
    label: "Untagged PII Columns",
    value: 3,
    hint: "in users, deliveries",
  },
  {
    id: "no-owners",
    label: "Assets Without Owners",
    value: 7,
    hint: "across 4 services",
  },
  {
    id: "orphaned-lineage",
    label: "Orphaned Lineage Nodes",
    value: 2,
    hint: "no upstream source",
  },
];

const minutesAgo = (mins: number) =>
  new Date(Date.now() - mins * 60_000).toISOString();

export const RECENT_ANALYSES: AnalysisCard[] = [
  {
    id: "1842",
    prNumber: 1842,
    repo: "foodieexpress/warehouse",
    title: "Drop legacy users.email column",
    severity: "breaking",
    columnsAffected: [
      { table: "users", column: "email" },
    ],
    downstreamCount: 4,
    downstreamSummary: "Marketing Cohorts · Churn Predictor v2 · daily_revenue_etl · CFO Weekly",
    owners: [OWNERS.priya, OWNERS.arjun],
    author: "ananya.k",
    createdAt: minutesAgo(3),
  },
  {
    id: "1841",
    prNumber: 1841,
    repo: "foodieexpress/payments-svc",
    title: "Rename payments.captured_at → payments.settled_at",
    severity: "breaking",
    columnsAffected: [
      { table: "payments", column: "captured_at" },
    ],
    downstreamCount: 2,
    downstreamSummary: "daily_revenue_etl · Fraud Detection v4",
    owners: [OWNERS.priya, OWNERS.arjun],
    author: "neel.k",
    createdAt: minutesAgo(28),
  },
  {
    id: "1840",
    prNumber: 1840,
    repo: "foodieexpress/orders-svc",
    title: "Rename orders.amount_cents → orders.total_cents",
    severity: "breaking",
    columnsAffected: [
      { table: "orders", column: "amount_cents" },
    ],
    downstreamCount: 3,
    downstreamSummary: "daily_revenue_etl · CFO Weekly · Fraud Detection v4",
    owners: [OWNERS.priya],
    author: "vikram.s",
    createdAt: minutesAgo(54),
  },
  {
    id: "1839",
    prNumber: 1839,
    repo: "foodieexpress/payments-svc",
    title: "Change payments.card_last_4 to NUMERIC(4)",
    severity: "breaking",
    columnsAffected: [
      { table: "payments", column: "card_last_4" },
    ],
    downstreamCount: 1,
    downstreamSummary: "Fraud Detection v4",
    owners: [OWNERS.arjun, OWNERS.kavya],
    author: "neel.k",
    createdAt: minutesAgo(96),
  },
  {
    id: "1838",
    prNumber: 1838,
    repo: "foodieexpress/warehouse",
    title: "Tighten users.email NOT NULL",
    severity: "warning",
    columnsAffected: [
      { table: "users", column: "email" },
    ],
    downstreamCount: 2,
    downstreamSummary: "Marketing Cohorts · customer_enrichment_etl",
    owners: [OWNERS.priya],
    author: "ananya.k",
    createdAt: minutesAgo(140),
  },
  {
    id: "1837",
    prNumber: 1837,
    repo: "foodieexpress/delivery-svc",
    title: "Drop deliveries.driver_phone (replaced by driver_id)",
    severity: "warning",
    columnsAffected: [
      { table: "deliveries", column: "driver_phone" },
    ],
    downstreamCount: 1,
    downstreamSummary: "Support Agent Console",
    owners: [OWNERS.kavya],
    author: "rohan.m",
    createdAt: minutesAgo(190),
  },
  {
    id: "1836",
    prNumber: 1836,
    repo: "foodieexpress/orders-svc",
    title: "Add nullable orders.promo_code",
    severity: "safe",
    columnsAffected: [
      { table: "orders", column: "promo_code" },
    ],
    downstreamCount: 0,
    downstreamSummary: "no downstream consumers",
    owners: [OWNERS.raj],
    author: "vikram.s",
    createdAt: minutesAgo(255),
  },
  {
    id: "1835",
    prNumber: 1835,
    repo: "foodieexpress/warehouse",
    title: "Drop restaurants.owner_contact",
    severity: "warning",
    columnsAffected: [
      { table: "restaurants", column: "owner_contact" },
    ],
    downstreamCount: 1,
    downstreamSummary: "Compliance weekly export",
    owners: [OWNERS.kavya],
    author: "ananya.k",
    createdAt: minutesAgo(330),
  },
  {
    id: "1834",
    prNumber: 1834,
    repo: "foodieexpress/orders-svc",
    title: "Add btree index on orders.created_at",
    severity: "safe",
    columnsAffected: [],
    downstreamCount: 0,
    downstreamSummary: "no schema change · perf only",
    owners: [OWNERS.raj],
    author: "vikram.s",
    createdAt: minutesAgo(420),
  },
  {
    id: "1833",
    prNumber: 1833,
    repo: "foodieexpress/warehouse",
    title: "Add orders.delivery_partner_id (FK)",
    severity: "safe",
    columnsAffected: [
      { table: "orders", column: "delivery_partner_id" },
    ],
    downstreamCount: 0,
    downstreamSummary: "no consumers reading new column",
    owners: [OWNERS.raj],
    author: "rohan.m",
    createdAt: minutesAgo(510),
  },
];

export function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function formatStatValue(stat: HeroStat, n: number): string {
  if (stat.format === "compact" && n >= 1000) {
    return `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k`;
  }
  return n.toLocaleString("en-IN");
}
