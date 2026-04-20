import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";

export function LineagePage() {
  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <PageHeader
        eyebrow="Lineage"
        title="Interactive lineage explorer"
        description="Trace any column from source system to dashboard. Click a node to see PRs that touched it."
      />

      <Card className="overflow-hidden">
        <CardContent className="flex h-[520px] items-center justify-center p-0 text-sm text-muted-foreground">
          ReactFlow canvas mounts here.
        </CardContent>
      </Card>
    </div>
  );
}
