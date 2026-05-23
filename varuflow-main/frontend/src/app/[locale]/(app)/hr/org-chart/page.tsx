"use client";

import { useEffect, useState } from "react";
import { GitFork, Loader2, ChevronRight, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface OrgNode {
  id: string;
  name: string;
  role: string | null;
  job_title: string | null;
  employment_type: string | null;
  reports_to_staff_id: string | null;
  children: OrgNode[];
}

function Node({ node, depth = 0 }: { node: OrgNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children.length > 0;

  return (
    <div className="select-none">
      <button
        onClick={() => setExpanded((x) => !x)}
        className="flex items-center gap-2 hover:bg-accent rounded px-2 py-1.5 w-full text-left"
        style={{ paddingLeft: `${depth * 24 + 8}px` }}
      >
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-sm flex-shrink-0">
          {node.name.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{node.name}</p>
          {node.job_title && <p className="text-xs text-muted-foreground truncate">{node.job_title}</p>}
        </div>
        {hasChildren && (
          <span className="text-xs text-muted-foreground mr-1">{node.children.length} report{node.children.length !== 1 ? "s" : ""}</span>
        )}
        {hasChildren ? (
          expanded ? <ChevronDown className="w-4 h-4 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 flex-shrink-0" />
        ) : null}
      </button>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <Node key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function OrgChartPage() {
  const [tree, setTree] = useState<OrgNode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/hr/org-chart")
      .then(setTree)
      .catch(() => toast.error("Failed to load org chart"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <GitFork className="w-6 h-6" />
        <h1 className="text-2xl font-semibold">Org Chart</h1>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : tree.length === 0 ? (
        <p className="text-sm text-muted-foreground">No employees found. Add employee profiles with reporting lines to build the hierarchy.</p>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          {tree.map((node) => (
            <Node key={node.id} node={node} depth={0} />
          ))}
        </div>
      )}
    </div>
  );
}
