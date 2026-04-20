import { useCallback, useEffect, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLineage } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const TABLE_NAMES = ["users", "orders", "payments", "restaurants", "deliveries"];

const TYPE_COLOR: Record<string, string> = {
  table:     "#3b82f6",
  dashboard: "#8b5cf6",
  mlmodel:   "#f59e0b",
  pipeline:  "#10b981",
};

const TYPE_LABEL: Record<string, string> = {
  table:     "Table",
  dashboard: "Dashboard",
  mlmodel:   "ML Model",
  pipeline:  "Pipeline",
};

function nodeStyle(type: string): React.CSSProperties {
  const color = TYPE_COLOR[type] ?? "#6b7280";
  return {
    background: `${color}18`,
    border: `1px solid ${color}50`,
    borderRadius: 8,
    padding: "8px 14px",
    fontSize: 12,
    fontFamily: "monospace",
    color: color,
    minWidth: 140,
  };
}

function buildFlowNodes(
  rawNodes: { id: string; label: string; type: string }[],
): Node[] {
  return rawNodes.map((n, i) => {
    const col = i === 0 ? 0 : Math.ceil(i / 2) * 250;
    const row = i === 0 ? 0 : ((i % 2 === 0 ? -1 : 1) * Math.ceil(i / 2)) * 100;
    return {
      id:       n.id,
      position: { x: col, y: row },
      data:     { label: n.label },
      style:    nodeStyle(n.type),
      type:     "default",
    };
  });
}

function buildFlowEdges(
  rawEdges: { from: string; to: string; direction?: string }[],
): Edge[] {
  return rawEdges.map((e, i) => ({
    id:        `e-${i}`,
    source:    e.from,
    target:    e.to,
    animated:  e.direction === "downstream",
    style:     { strokeWidth: 1.5, stroke: "#6b7280" },
  }));
}

export function LineagePage() {
  const [selectedTable, setSelectedTable] = useState("users");
  const lineage = useLineage(selectedTable);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!lineage.data) return;
    setNodes(buildFlowNodes(lineage.data.nodes));
    setEdges(buildFlowEdges(lineage.data.edges));
  }, [lineage.data, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const source = (lineage.data as any)?.source;

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <PageHeader
        eyebrow="Lineage"
        title="Interactive lineage explorer"
        description="Trace any table from source to downstream dashboards, ML models, and pipelines."
      />

      {/* Table selector */}
      <div className="flex flex-wrap items-center gap-2">
        {TABLE_NAMES.map((t) => (
          <Button
            key={t}
            variant={selectedTable === t ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedTable(t)}
            className="font-mono text-xs"
          >
            {t}
          </Button>
        ))}

        <div className="ml-auto flex flex-wrap gap-2">
          {Object.entries(TYPE_LABEL).map(([type, label]) => (
            <span key={type} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: TYPE_COLOR[type] }}
              />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="relative h-[520px]">
            {lineage.isLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/60 text-sm text-muted-foreground">
                Loading lineage…
              </div>
            )}
            {lineage.isError && (
              <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-destructive">
                Failed to load lineage — showing stub data
              </div>
            )}
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              attributionPosition="bottom-right"
            >
              <Background gap={16} size={1} />
              <Controls />
              <MiniMap
                nodeColor={(n) => {
                  const style = n.style as React.CSSProperties;
                  return String(style?.border ?? "#6b7280").split(" ")[2] ?? "#6b7280";
                }}
                maskColor="rgba(0,0,0,0.3)"
              />
            </ReactFlow>
          </div>
        </CardContent>
      </Card>

      {/* Stats row */}
      {lineage.data && (
        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <span>
            <span className="font-medium text-foreground">{lineage.data.nodes.length}</span> nodes
          </span>
          <span>
            <span className="font-medium text-foreground">{lineage.data.edges.length}</span> edges
          </span>
          {source && (
            <Badge variant="outline" className={cn("text-[10px]", source === "om" ? "border-success/40 text-success" : "border-border/60 text-muted-foreground")}>
              {source === "om" ? "live OM" : "demo data"}
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
