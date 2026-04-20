import { Link, useParams } from "react-router-dom";
import { ArrowLeft, GitPullRequest } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function PRDetailPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <Button variant="ghost" size="sm" asChild className="text-muted-foreground">
        <Link to="/">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to overview
        </Link>
      </Button>

      <PageHeader
        eyebrow={`Pull request · #${id ?? "—"}`}
        title="Drop legacy customer_email column"
        description="acme/warehouse · main ← chore/drop-legacy-email"
        actions={
          <>
            <Badge variant="destructive">breaking</Badge>
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

        <TabsContent value="impact">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Affected downstream assets
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Detailed impact analysis renders here once the backend is wired
              up.
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="diff">
          <Card>
            <CardContent className="p-6 font-mono text-xs text-muted-foreground">
              <pre>{`- email VARCHAR(320) NOT NULL\n+ -- removed`}</pre>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="lineage">
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              Lineage subgraph appears here.
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
