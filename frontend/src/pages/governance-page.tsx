import { PageHeader } from "@/components/layout/page-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";

const metrics = [
  { label: "Mean time to detect", value: "0.8s" },
  { label: "Breaking PRs blocked", value: "23" },
  { label: "Coverage", value: "94%" },
  { label: "Active reviewers", value: "12" },
];

export function GovernancePage() {
  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <PageHeader
        eyebrow="Governance"
        title="Governance pulse"
        description="A weekly read on how your data contracts are holding up across teams."
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {metrics.map((m) => (
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

      <Card>
        <CardHeader>
          <CardDescription>
            Detailed governance charts will live here once metrics are wired in.
          </CardDescription>
        </CardHeader>
        <CardContent className="h-64 border-t border-border/60 bg-muted/20" />
      </Card>
    </div>
  );
}
