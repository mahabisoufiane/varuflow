"use client";
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api-client";
import pageStyles from "./page.module.scss";

type Severity = "info" | "warning" | "critical";

interface Anomaly {
  id: string;
  type: string;
  severity: Severity;
  title: string;
  body: string;
  reference?: string;
  is_read: boolean;
  pushed_at: string;
}

interface UnreadCount {
  total: number;
  critical: number;
}

const severityClass: Record<Severity, string> = {
  info: "bg-blue-100 text-blue-800",
  warning: "bg-yellow-100 text-yellow-800",
  critical: "bg-red-100 text-red-800",
};

const SEV_MODULE: Record<Severity, keyof typeof pageStyles> = {
  info:     "severityInfo",
  warning:  "severityWarning",
  critical: "severityCritical",
};

export default function AnomaliesPage() {
  const [items, setItems] = useState<Anomaly[]>([]);
  const [unread, setUnread] = useState<UnreadCount>({ total: 0, critical: 0 });
  const [severityFilter, setSeverityFilter] = useState<"all" | Severity>("all");
  const [isReadFilter, setIsReadFilter] = useState<"all" | "unread">("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchUnread = useCallback(async () => {
    try {
      const data = await api.get<UnreadCount>("/api/anomalies/unread-count");
      setUnread(data);
    } catch {
      // non-critical
    }
  }, []);

  const fetchAnomalies = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (severityFilter !== "all") params.set("severity", severityFilter);
      if (isReadFilter === "unread") params.set("is_read", "false");
      const query = params.toString() ? `?${params.toString()}` : "";
      setItems(await api.get<Anomaly[]>(`/api/anomalies${query}`));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load anomalies");
    } finally {
      setLoading(false);
    }
  }, [severityFilter, isReadFilter]);

  useEffect(() => {
    fetchUnread();
    fetchAnomalies();
  }, [fetchUnread, fetchAnomalies]);

  async function markAllRead() {
    setError("");
    try {
      await api.post("/api/anomalies/read-all", {});
      await Promise.all([fetchUnread(), fetchAnomalies()]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to mark all read");
    }
  }

  async function markRead(id: string) {
    try {
      await api.post(`/api/anomalies/${id}/read`, {});
      await Promise.all([fetchUnread(), fetchAnomalies()]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to mark read");
    }
  }

  const SEVERITY_TABS: Array<"all" | Severity> = ["all", "info", "warning", "critical"];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Anomaly Notifications</h1>
        <div className="flex items-center gap-3">
          {unread.total > 0 && (
            <span className="inline-flex items-center rounded-full bg-red-100 text-red-800 px-3 py-1 text-sm font-medium">
              {unread.total} unread ({unread.critical} critical)
            </span>
          )}
          <Button variant="outline" size="sm" onClick={markAllRead}>
            Mark All Read
          </Button>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1">
          {SEVERITY_TABS.map((s) => (
            <button
              key={s}
              onClick={() => setSeverityFilter(s)}
              className={`px-3 py-1 rounded text-sm border transition-colors ${
                severityFilter === s
                  ? "bg-foreground text-background"
                  : "hover:bg-muted"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(["all", "unread"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setIsReadFilter(f)}
              className={`px-3 py-1 rounded text-sm border transition-colors ${
                isReadFilter === f
                  ? "bg-foreground text-background"
                  : "hover:bg-muted"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <Card>
        <CardContent className="pt-4">
          {loading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Body</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead>Read</TableHead>
                  <TableHead>Pushed At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted-foreground">
                      No anomalies found.
                    </TableCell>
                  </TableRow>
                )}
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-xs font-mono">{item.type}</TableCell>
                    <TableCell>
                      <span
                        className={pageStyles[SEV_MODULE[item.severity]]}
                      >
                        {item.severity}
                      </span>
                    </TableCell>
                    <TableCell className="font-medium">{item.title}</TableCell>
                    <TableCell className="max-w-xs">
                      <span title={item.body}>
                        {item.body.length > 100 ? item.body.slice(0, 100) + "…" : item.body}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs font-mono">{item.reference ?? "—"}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-block w-2 h-2 rounded-full ${
                          item.is_read ? "bg-gray-300" : "bg-orange-400"
                        }`}
                        title={item.is_read ? "Read" : "Unread"}
                      />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(item.pushed_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      {!item.is_read && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => markRead(item.id)}
                        >
                          Mark Read
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
