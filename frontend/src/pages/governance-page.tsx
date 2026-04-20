import { AlertCircle, Shield, Tag, Users } from "lucide-react";

import { AnimatedNumber } from "@/components/animated-number";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGovernancePulse } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const STATIC_METRICS = [
  { label: "Mean time to detect", value: "0.8s" },
  { label: "Breaking PRs blocked", value: "23" },
  { label: "Coverage", value: "94%" },
  { label: "Active reviewers", value: "12" },
];

export function GovernancePage() {
  const pulse = useGovernancePulse();
  const source = (pulse.data as any)?.source;

  const liveItems = pulse.data
    ? [
        {
          id: "untagged-pii",
          label: "Untagged PII Columns",
          value: pulse.data.untagged_pii,
          hint: "Columns that appear PII-ish but carry no PII classification tag",
          icon: Tag,
          warn: pulse.data.untagged_pii > 0,
        },
        {
          id: "no-owners",
          label: "Assets Without Owners",
          value: pulse.data.assets_no_owner,
          hint: "Tables or other assets with no owner set in OpenMetadata",
          icon: Users,
          warn: pulse.data.assets_no_owner > 0,
        },
        {
          id: "orphaned",
          label: "Orphaned Lineage Nodes",
          value: pulse.data.orphaned_nodes,
          hint: "Nodes with no upstream source detected in the lineage graph",
          icon: AlertCircle,
          warn: pulse.data.orphaned_nodes > 0,
        },
      ]
    : null;

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <PageHeader
        eyebrow="Governance"
        title="Governance pulse"
        description="A weekly read on how your data contracts are holding up across teams."
      />

      {/* Static performance metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STATIC_METRICS.map((m) => (
          <Card key={m.label}>
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase tracking-wider">
                {m.label}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="font-mono text-3xl font-semibold tracking-tight">
                {m.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Live governance health */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            <Shield className="h-3.5 w-3.5" />
            Data health snapshot
          </h2>
          {source && (
            <Badge
              variant="outline"
              className={cn(
                "text-[10px]",
                source === "om"
                  ? "border-success/40 text-success"
                  : "border-border/60 text-muted-foreground",
              )}
            >
              {source === "om" ? "live OpenMetadata" : "demo data"}
            </Badge>
          )}
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {pulse.isLoading
            ? [0, 1, 2].map((i) => (
                <Card key={i} className="p-6">
                  <Skeleton className="mb-4 h-4 w-32" />
                  <Skeleton className="h-10 w-16" />
                  <Skeleton className="mt-2 h-3 w-full" />
                </Card>
              ))
            : (liveItems ?? []).map((item) => {
                const Icon = item.icon;
                return (
                  <Card
                    key={item.id}
                    className={cn(
                      "p-6",
                      item.warn && "ring-1 ring-inset ring-warning/30",
                    )}
                  >
                    <div className="mb-4 flex items-center justify-between">
                      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                        {item.label}
                      </span>
                      <Icon
                        className={cn(
                          "h-4 w-4",
                          item.warn ? "text-warning" : "text-muted-foreground",
                        )}
                      />
                    </div>
                    <AnimatedNumber
                      value={item.value}
                      className={cn(
                        "block font-mono text-4xl font-semibold heading-tight",
                        item.value === 0
                          ? "text-success"
                          : "text-warning",
                      )}
                    />
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      {item.hint}
                    </p>
                  </Card>
                );
              })}
        </div>
      </div>

      {/* Placeholder for charts */}
      <Card>
        <CardHeader>
          <CardDescription>
            Trend charts and policy violation history will live here once
            time-series metrics are wired in.
          </CardDescription>
        </CardHeader>
        <CardContent className="h-64 border-t border-border/60 bg-muted/20" />
      </Card>
    </div>
  );
}
