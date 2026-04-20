import { Link, useParams } from "react-router-dom";
import { ArrowLeft, GitPullRequest, Network, User } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/layout/page-header";
import { OwnerStack } from "@/components/owner-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useLineage } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import type { AnalysisCard } from "@/types/api";

const SEV_BADGE: Record<string, string> = {
  breaking: "bg-destructive/15 text-destructive ring-1 ring-inset ring-destructive/40",
  warning:  "bg-warning/15 text-warning ring-1 ring-inset ring-warning/30",
  safe:     "bg-success/15 text-success ring-1 ring-inset ring-success/30",
};

function usePRDetail(id: string | undefined) {
  return useQuery({
    queryKey: ["pr", id],
    queryFn: async () => {
      const { data } = await api.get<AnalysisCard>(`/api/pr/${id}`);
      return data;
    },
    enabled: Boolean(id),
    retry: 1,
  });
}

function ImpactTab({ pr }: { pr: AnalysisCard }) {
  return (
    <div className="space-y-4">
      {/* Downstream impact summary */}
      <Card className="p-5">
        <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Downstream Impact
        </p>
        <div className="flex items-center gap-2">
          <Network className={cn("h-4 w-4", pr.downstreamCount > 0 ? "text-destructive" : "text-muted-foreground")} />
          <span className="text-sm font-medium">
            {pr.downstreamCount === 0
              ? "No downstream impact detected"
              : `${pr.downstreamCount} ${pr.downstreamCount === 1 ? "asset" : "assets"} affected`}
          </span>
        </div>
        {pr.downstreamCount > 0 && (
          <p className="mt-1 text-sm text-muted-foreground">{pr.downstreamSummary}</p>
        )}
      </Card>

      {/* Affected columns */}
      {pr.columnsAffected.length > 0 && (
        <Card className="p-5">
          <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Columns Affected ({pr.columnsAffected.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {pr.columnsAffected.map((c) => (
              <Badge
                key={`${c.table}.${c.column}`}
                variant="outline"
                className="font-mono text-xs"
              >
                {c.table}.{c.column}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      {/* Owners */}
      {pr.owners.length > 0 && (
        <Card className="p-5">
          <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Owners to Notify
          </p>
          <div className="space-y-2">
            {pr.owners.map((o) => (
              <div key={o.id} className="flex items-center gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full border border-border/60 bg-muted/40">
                  <User className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium">{o.name}</p>
                  <p className="text-xs text-muted-foreground">{o.role}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function LineageTab({ pr }: { pr: AnalysisCard }) {
  const table = pr.columnsAffected[0]?.table;
  const lineage = useLineage(table ?? "");

  if (!table) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          No columns affected — no lineage to show.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Lineage for <span className="font-mono text-foreground">{table}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {lineage.isLoading && <Skeleton className="h-40 w-full" />}
        {lineage.data && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {lineage.data.nodes.map((n) => (
                <span
                  key={n.id}
                  className={cn(
                    "rounded-md border px-2.5 py-1 font-mono text-xs",
                    n.id === table || n.label === table
                      ? "border-blue-500/40 bg-blue-500/10 text-blue-400"
                      : "border-border/60 bg-background/40 text-muted-foreground",
                  )}
                >
                  {n.label}
                  <span className="ml-1 text-[10px] opacity-60">{n.type}</span>
                </span>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground">
              {lineage.data.edges.length} lineage edge{lineage.data.edges.length !== 1 ? "s" : ""} from this table
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function PRDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: pr, isLoading, isError } = usePRDetail(id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !pr || (pr as any).error) {
    return (
      <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
        <Button variant="ghost" size="sm" asChild className="text-muted-foreground">
          <Link to="/"><ArrowLeft className="h-3.5 w-3.5" /> Back to overview</Link>
        </Button>
        <p className="text-sm text-muted-foreground">PR #{id} not found.</p>
      </div>
    );
  }

  const sevClass = SEV_BADGE[pr.severity] ?? SEV_BADGE.safe;

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <Button variant="ghost" size="sm" asChild className="text-muted-foreground">
        <Link to="/"><ArrowLeft className="h-3.5 w-3.5" /> Back to overview</Link>
      </Button>

      <PageHeader
        eyebrow={`Pull request · ${pr.repo} · #${pr.prNumber}`}
        title={pr.title}
        description={`Author: ${pr.author}`}
        actions={
          <>
            <span className={cn("rounded-md px-2.5 py-1 text-xs font-medium", sevClass)}>
              {pr.severity}
            </span>
            <OwnerStack owners={pr.owners} />
            <Button variant="outline" size="sm">
              View on GitHub
              <GitPullRequest className="h-3.5 w-3.5" />
            </Button>
          </>
        }
      />

      <Tabs defaultValue="impact">
        <TabsList>
          <TabsTrigger value="impact">Impact</TabsTrigger>
          <TabsTrigger value="diff">Schema diff</TabsTrigger>
          <TabsTrigger value="lineage">Lineage</TabsTrigger>
        </TabsList>

        <TabsContent value="impact" className="mt-4">
          <ImpactTab pr={pr} />
        </TabsContent>

        <TabsContent value="diff" className="mt-4">
          <Card>
            <CardContent className="p-6 font-mono text-xs text-muted-foreground">
              <pre>
                {pr.columnsAffected
                  .map((c) => `- ${c.table}.${c.column}  -- changed`)
                  .join("\n") || "No schema diff recorded"}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lineage" className="mt-4">
          <LineageTab pr={pr} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
