import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  FileCheck,
  Network,
  Shield,
  TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { AnimatedNumber } from "@/components/animated-number";
import { PageHeader } from "@/components/layout/page-header";
import { OwnerStack } from "@/components/owner-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGovernancePulse, useRecentAnalyses } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import {
  GOVERNANCE_PULSE,
  HERO_STATS,
  RECENT_ANALYSES,
  formatStatValue,
  relativeTime,
  type AnalysisCard,
  type HeroStat,
  type Severity,
} from "@/lib/mock-data";
import type { GovernancePulse } from "@/types/api";

const HERO_ICONS: Record<string, LucideIcon> = {
  "prs-today": Activity,
  "breaking-caught": AlertTriangle,
  "assets-protected": Shield,
  "migration-plans": FileCheck,
};

const SEVERITY_BADGE: Record<
  Severity,
  { label: string; className: string }
> = {
  safe: {
    label: "Safe",
    className: "bg-success/15 text-success ring-1 ring-inset ring-success/30",
  },
  breaking: {
    label: "Breaking",
    className:
      "bg-destructive/15 text-destructive-foreground/90 ring-1 ring-inset ring-destructive/40",
  },
  warning: {
    label: "Warning",
    className: "bg-warning/15 text-warning ring-1 ring-inset ring-warning/30",
  },
};


// ---------------------------------------------------------------------------
// Hero stat card
// ---------------------------------------------------------------------------

function HeroStatCard({ stat }: { stat: HeroStat }) {
  const Icon = HERO_ICONS[stat.id] ?? Activity;
  const isDanger = stat.intent === "danger";
  const deltaPositive = (stat.delta ?? 0) >= 0;

  return (
    <Card
      className={cn(
        "relative flex flex-col justify-between gap-6 overflow-hidden p-6 transition-colors hover:border-border/80",
        isDanger && "ring-1 ring-inset ring-destructive/20",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {stat.label}
        </span>
        <div
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-md border",
            isDanger
              ? "border-destructive/30 bg-destructive/10 text-destructive"
              : "border-border/80 bg-background/60 text-muted-foreground",
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </div>
      </div>

      <div className="space-y-1.5">
        <AnimatedNumber
          value={stat.value}
          format={(n) => formatStatValue(stat, n)}
          className={cn(
            "block font-mono text-[32px] font-semibold leading-none heading-tight",
            isDanger ? "text-destructive-foreground" : "text-foreground",
          )}
        />
        {stat.delta !== undefined ? (
          <div
            className={cn(
              "flex items-center gap-1 text-xs",
              deltaPositive
                ? isDanger
                  ? "text-destructive"
                  : "text-success"
                : "text-muted-foreground",
            )}
          >
            <TrendingUp
              className={cn(
                "h-3 w-3",
                !deltaPositive && "rotate-180",
              )}
            />
            <span className="font-medium">
              {deltaPositive ? "+" : ""}
              {stat.delta}%
            </span>
            {stat.deltaLabel ? (
              <span className="text-muted-foreground">{stat.deltaLabel}</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// PR feed card
// ---------------------------------------------------------------------------

function PRAnalysisCard({ analysis }: { analysis: AnalysisCard }) {
  const navigate = useNavigate();
  const sev = SEVERITY_BADGE[analysis.severity];

  return (
    <Card
      role="link"
      tabIndex={0}
      onClick={() => navigate(`/pr/${analysis.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate(`/pr/${analysis.id}`);
        }
      }}
      className="group cursor-pointer p-6 transition-all hover:border-border/80 hover:bg-card/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider",
                sev.className,
              )}
            >
              {sev.label}
            </span>
            <span className="font-mono text-xs text-muted-foreground">
              {analysis.repo}
              <span className="mx-1.5 text-muted-foreground/60">·</span>
              #{analysis.prNumber}
            </span>
          </div>
          <h3 className="text-[15px] font-medium leading-snug text-foreground heading-tight">
            {analysis.title}
          </h3>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className="text-xs text-muted-foreground">
            {relativeTime(analysis.createdAt)}
          </span>
          <OwnerStack owners={analysis.owners} />
        </div>
      </div>

      {analysis.columnsAffected.length > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          {analysis.columnsAffected.map((c) => (
            <Badge
              key={`${c.table}.${c.column}`}
              variant="outline"
              className="border-border/80 bg-background/40 font-mono text-[11px] text-muted-foreground"
            >
              {c.table}.{c.column}
            </Badge>
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex items-end justify-between gap-3 border-t border-border/60 pt-4">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-1.5 text-xs">
            <Network
              className={cn(
                "h-3 w-3",
                analysis.downstreamCount === 0
                  ? "text-muted-foreground"
                  : analysis.severity === "breaking"
                    ? "text-destructive"
                    : analysis.severity === "warning"
                      ? "text-warning"
                      : "text-muted-foreground",
              )}
            />
            <span className="font-medium text-foreground">
              {analysis.downstreamCount === 0
                ? "No downstream impact"
                : `Breaks ${analysis.downstreamCount} ${analysis.downstreamCount === 1 ? "asset" : "assets"}`}
            </span>
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {analysis.downstreamSummary}
          </p>
        </div>

        <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground transition-colors group-hover:text-foreground">
          View Analysis
          <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </Card>
  );
}

function PRAnalysisSkeleton() {
  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-5 w-20" />
      </div>
      <Skeleton className="h-3 w-full" />
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Governance pulse sidebar
// ---------------------------------------------------------------------------

function GovernancePulseCard({ live }: { live?: GovernancePulse }) {
  const items = live
    ? [
        { id: "untagged-pii",     label: "Untagged PII Columns",     value: live.untagged_pii,    hint: "in users, deliveries" },
        { id: "no-owners",        label: "Assets Without Owners",    value: live.assets_no_owner, hint: "across 4 services" },
        { id: "orphaned-lineage", label: "Orphaned Lineage Nodes",   value: live.orphaned_nodes,  hint: "no upstream source" },
      ]
    : GOVERNANCE_PULSE;

  return (
    <Card className="sticky top-20 flex flex-col gap-5 p-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Governance Pulse
          </span>
          <h2 className="text-base font-semibold heading-tight">
            Health snapshot
          </h2>
        </div>
        <Shield className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="space-y-2">
        {items.map((g) => (
          <div
            key={g.id}
            className="flex items-baseline justify-between rounded-lg border border-border/60 bg-background/40 p-3"
          >
            <div className="min-w-0 space-y-0.5">
              <p className="truncate text-xs text-muted-foreground">{g.label}</p>
              <p className="truncate text-[11px] text-muted-foreground/80">
                {g.hint}
              </p>
            </div>
            <AnimatedNumber
              value={g.value}
              className={cn(
                "shrink-0 font-mono text-2xl font-semibold heading-tight",
                g.value === 0 ? "text-muted-foreground" : "text-warning",
              )}
            />
          </div>
        ))}
      </div>

      <Button variant="outline" size="sm" className="justify-between">
        Run Full Audit
        <ArrowUpRight className="h-3.5 w-3.5" />
      </Button>
    </Card>
  );
}

function GovernancePulseSkeleton() {
  return (
    <Card className="space-y-4 p-6">
      <Skeleton className="h-5 w-40" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-14 w-full rounded-lg" />
      ))}
      <Skeleton className="h-9 w-full" />
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function HomePage() {
  const analysesQuery = useRecentAnalyses();
  const pulseQuery = useGovernancePulse();

  const backendDown = analysesQuery.isError || pulseQuery.isError;
  const analyses = analysesQuery.data ?? (analysesQuery.isError ? RECENT_ANALYSES : undefined);
  const loading = analysesQuery.isLoading || pulseQuery.isLoading;

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      {backendDown && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          Backend unreachable — showing cached demo data
        </div>
      )}

      <PageHeader
        eyebrow="Overview"
        title="Schema activity at a glance"
        description="Every pull request, scored against your live data lineage. FluxGuardian flags breaking changes before they reach production."
      />

      {/* Hero stats */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {HERO_STATS.map((s) => <HeroStatCard key={s.id} stat={s} />)}
      </section>

      {/* Main grid: feed + pulse */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Recent Analyses
            </h2>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1 text-xs text-muted-foreground"
            >
              View all
              <ArrowUpRight className="h-3 w-3" />
            </Button>
          </div>

          <div className="space-y-3">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <PRAnalysisSkeleton key={i} />
                ))
              : (analyses ?? RECENT_ANALYSES).map((a) => (
                  <PRAnalysisCard key={a.id} analysis={a} />
                ))}
          </div>
        </section>

        <aside className="lg:col-span-1">
          {pulseQuery.isLoading ? (
            <GovernancePulseSkeleton />
          ) : (
            <GovernancePulseCard live={pulseQuery.data} />
          )}
        </aside>
      </div>
    </div>
  );
}
