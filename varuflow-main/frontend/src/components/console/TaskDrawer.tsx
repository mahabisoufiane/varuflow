// File: src/components/console/TaskDrawer.tsx
// Purpose: Region 4 of the operator console — a bottom-anchored, collapsible
// drawer showing background jobs / automation runs / audit events, similar in
// spirit to a task-progress log. It polls the existing GET /api/analytics/activity
// feed and merges it with client-side optimistic tasks from TaskDrawerContext
// (invoice sends, stock syncs, Peppol delivery, AI cards report progress by
// calling pushTask/updateTask). No backend changes; degrades silently if the
// feed is plan-gated.

"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Clock, Loader2, CheckCircle2, XCircle, ChevronUp, ChevronDown, ListChecks, Eraser,
  type LucideIcon,
} from "lucide-react";

import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useTaskDrawer, type ConsoleTask, type TaskStatus } from "@/components/console/TaskDrawerContext";

const POLL_MS = 15_000;

interface ActivityItem {
  type: string;
  description: string;
  created_at: string;
}

// Map the analytics-activity event types to i18n label keys (console.tasks.event.*).
const ACTIVITY_LABEL: Record<string, string> = {
  invoice_created: "tasks.event.invoiceCreated",
  invoice_paid: "tasks.event.invoicePaid",
  stock_movement: "tasks.event.stockMovement",
  purchase_order_received: "tasks.event.poReceived",
  new_customer: "tasks.event.newCustomer",
};

const STATUS_META: Record<TaskStatus, { icon: LucideIcon; className: string; spin?: boolean }> = {
  pending: { icon: Clock, className: "text-muted-foreground" },
  running: { icon: Loader2, className: "text-blue-500", spin: true },
  success: { icon: CheckCircle2, className: "text-emerald-500" },
  failed: { icon: XCircle, className: "text-red-500" },
};

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86_400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86_400)}d`;
}

export default function TaskDrawer() {
  const t = useTranslations("console");
  const { tasks: localTasks, isOpen, toggle, clearFinished } = useTaskDrawer();
  const [remote, setRemote] = useState<ConsoleTask[]>([]);

  // Poll the activity feed; keep the last good result on error (e.g. 403 on FREE).
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const list = await api.get<ActivityItem[]>("/api/analytics/activity?limit=20", { silent: true });
        if (!active) return;
        setRemote(
          list.map((a, i) => ({
            id: `act-${a.created_at}-${i}`,
            label: t((ACTIVITY_LABEL[a.type] ?? "tasks.event.generic") as Parameters<typeof t>[0]),
            detail: a.description,
            status: "success" as TaskStatus,
            source: "job" as const,
            createdAt: a.created_at,
          }))
        );
      } catch {
        /* silent — activity feed is optional / plan-gated */
      }
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [t]);

  const merged = [...localTasks, ...remote].sort(
    (a, b) => +new Date(b.createdAt) - +new Date(a.createdAt)
  );
  const runningCount = localTasks.filter((x) => x.status === "running" || x.status === "pending").length;
  const latest = merged[0];

  return (
    <section className="shrink-0 border-t bg-background" aria-label={t("tasks.title")}>
      {/* Collapsed/expanded header bar */}
      <button
        type="button"
        onClick={toggle}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-accent/40"
      >
        <ListChecks className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="font-medium text-foreground">{t("tasks.title")}</span>
        {runningCount > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-600">
            <Loader2 className="h-3 w-3 animate-spin" />
            {runningCount} {t("tasks.status.running")}
          </span>
        )}
        {!isOpen && latest && (
          <span className="ml-1 truncate text-xs text-muted-foreground">
            · {latest.label} · {timeAgo(latest.createdAt)}
          </span>
        )}
        <span className="ml-auto shrink-0 text-muted-foreground">
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        </span>
      </button>

      {/* Expanded list */}
      {isOpen && (
        <div className="flex h-[38vh] flex-col border-t">
          <div className="flex items-center justify-end gap-2 px-3 py-1.5">
            <button
              type="button"
              onClick={clearFinished}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Eraser className="h-3.5 w-3.5" />
              {t("tasks.clear")}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-3">
            {merged.length === 0 ? (
              <p className="px-2 py-8 text-center text-xs text-muted-foreground">{t("tasks.empty")}</p>
            ) : (
              <ul className="space-y-0.5">
                {merged.map((task) => {
                  const meta = STATUS_META[task.status];
                  const Icon = meta.icon;
                  return (
                    <li
                      key={task.id}
                      className="flex items-center gap-2.5 rounded-md px-2 py-1.5 hover:bg-accent/40"
                    >
                      <Icon className={cn("h-4 w-4 shrink-0", meta.className, meta.spin && "animate-spin")} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-foreground">{task.label}</p>
                        {task.detail && (
                          <p className="truncate text-xs text-muted-foreground">{task.detail}</p>
                        )}
                      </div>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {timeAgo(task.createdAt)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
