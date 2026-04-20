import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  ShieldAlert,
  Zap,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAnalyzeDiff } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import type { AffectedAsset, BackendSeverity, BlastRadiusReport } from "@/types/api";

const DEMO_DIFF = `--- a/migrations/005.sql
+++ b/migrations/005.sql
@@ -0,0 +1,1 @@
+ALTER TABLE users RENAME COLUMN email TO contact_email;`;

const SEV_LABEL: Record<BackendSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

const SEV_CLASS: Record<BackendSeverity, string> = {
  critical: "bg-destructive/15 text-destructive",
  high:     "bg-orange-500/15 text-orange-400",
  medium:   "bg-warning/15 text-warning",
  low:      "bg-muted text-muted-foreground",
};

function SeverityChip({ sev }: { sev: BackendSeverity }) {
  const icons = {
    critical: AlertCircle,
    high: AlertTriangle,
    medium: AlertTriangle,
    low: CheckCircle2,
  };
  const Icon = icons[sev];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium",
        sev === "critical" && "border-destructive/30 bg-destructive/10 text-destructive",
        sev === "high"     && "border-orange-500/30 bg-orange-500/10 text-orange-400",
        sev === "medium"   && "border-warning/30 bg-warning/10 text-warning",
        sev === "low"      && "border-border/60 bg-muted/40 text-muted-foreground",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {SEV_LABEL[sev]}
    </span>
  );
}

function AssetRow({ a }: { a: AffectedAsset }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{a.name}</p>
        <p className="truncate font-mono text-[11px] text-muted-foreground">{a.fqn}</p>
        {a.reason && (
          <p className="mt-0.5 text-[11px] text-muted-foreground/70">{a.reason}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge variant="outline" className="text-[10px]">{a.asset_type}</Badge>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium uppercase", SEV_CLASS[a.severity])}>
          {a.severity}
        </span>
      </div>
    </div>
  );
}

function ReportCard({ report }: { report: BlastRadiusReport }) {
  const [jsonOpen, setJsonOpen] = useState(false);
  const sc = report.schema_change;

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Analysis Result
          </p>
          <p className="text-base font-medium">{report.summary_one_line}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {report.pii_involved && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-orange-500/30 bg-orange-500/10 px-2.5 py-1 text-sm font-medium text-orange-400">
              <ShieldAlert className="h-3.5 w-3.5" />
              PII Risk
            </span>
          )}
          {report.requires_governance_approval && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-yellow-500/30 bg-yellow-500/10 px-2.5 py-1 text-sm font-medium text-yellow-400">
              <AlertTriangle className="h-3.5 w-3.5" />
              Governance Approval Required
            </span>
          )}
          <SeverityChip sev={report.overall_severity} />
        </div>
      </Card>

      {/* Schema change */}
      <Card className="p-5">
        <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Detected Change
        </p>
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border/60 bg-background/40 px-3 py-2 font-mono text-xs">
          <Badge variant="outline" className="text-[10px] uppercase">{sc.change_type}</Badge>
          <span className="text-foreground">{sc.table}</span>
          {sc.old_column && (
            <>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground line-through">{sc.old_column}</span>
            </>
          )}
          {sc.new_column && (
            <span className="text-success">→ {sc.new_column}</span>
          )}
          {sc.old_type && (
            <span className="text-muted-foreground line-through">{sc.old_type}</span>
          )}
          {sc.new_type && (
            <span className="text-success">→ {sc.new_type}</span>
          )}
        </div>
        {report.pii_classifications.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {report.pii_classifications.map((tag) => (
              <Badge key={tag} variant="outline" className="border-orange-500/30 text-[10px] text-orange-400">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </Card>

      {/* Affected assets */}
      <Card className="p-5">
        <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Affected Assets ({report.affected_assets.length})
          {report.total_owners_to_notify > 0 && (
            <span className="ml-2 text-muted-foreground/70 normal-case">
              · {report.total_owners_to_notify} owner{report.total_owners_to_notify > 1 ? "s" : ""} to notify
            </span>
          )}
        </p>
        {report.affected_assets.length === 0 ? (
          <p className="text-sm text-muted-foreground">No downstream impact detected.</p>
        ) : (
          <div className="divide-y divide-border/60">
            {report.affected_assets.map((a) => (
              <AssetRow key={a.fqn} a={a} />
            ))}
          </div>
        )}
        {report.unique_owner_emails.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border/60 pt-4">
            {report.unique_owner_emails.map((email) => (
              <span key={email} className="rounded-md border border-border/60 bg-background/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                {email}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* Collapsible JSON */}
      <div>
        <button
          onClick={() => setJsonOpen((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          {jsonOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {jsonOpen ? "Hide" : "Show"} raw JSON
        </button>
        {jsonOpen && (
          <pre className="mt-2 overflow-auto rounded-lg border border-border/60 bg-muted/30 p-4 font-mono text-[11px] leading-relaxed text-foreground">
            {JSON.stringify(report, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

export function AnalyzePage() {
  const [diff, setDiff] = useState("");
  const mutation = useAnalyzeDiff();

  function handleAnalyze() {
    if (diff.trim()) mutation.mutate(diff.trim());
  }

  function handleDemo() {
    setDiff(DEMO_DIFF);
    mutation.reset();
  }

  const reports = mutation.data ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-10">
      <PageHeader
        eyebrow="Analyze"
        title="Blast radius analysis"
        description="Paste a SQL migration diff and get an instant impact report — affected assets, PII exposure, and migration hints."
      />

      <Card className="space-y-4 p-6">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            SQL Migration Diff
          </p>
          <Button variant="ghost" size="sm" onClick={handleDemo} className="text-xs text-muted-foreground">
            <Zap className="mr-1.5 h-3 w-3" />
            Load demo diff
          </Button>
        </div>
        <textarea
          value={diff}
          onChange={(e) => setDiff(e.target.value)}
          placeholder={"--- a/migrations/005.sql\n+++ b/migrations/005.sql\n@@ ... @@\n+ALTER TABLE users ..."}
          rows={10}
          className="w-full resize-none rounded-md border border-border/60 bg-background/40 p-3 font-mono text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <div className="flex items-center justify-between gap-4">
          <p className="text-[11px] text-muted-foreground">
            Supports ALTER TABLE, DROP COLUMN, RENAME COLUMN, ADD COLUMN
          </p>
          <Button
            onClick={handleAnalyze}
            disabled={!diff.trim() || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            {mutation.isPending ? "Analyzing…" : "Analyze"}
          </Button>
        </div>
      </Card>

      {mutation.isError && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          Backend error — make sure the backend is running at localhost:8000
        </div>
      )}

      {mutation.isSuccess && reports.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          No schema changes detected in the provided diff.
        </div>
      )}

      {reports.length > 0 && (
        <div className="space-y-8">
          {reports.map((r, i) => (
            <div key={i}>
              {reports.length > 1 && (
                <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Change {i + 1} of {reports.length}
                </p>
              )}
              <ReportCard report={r} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
