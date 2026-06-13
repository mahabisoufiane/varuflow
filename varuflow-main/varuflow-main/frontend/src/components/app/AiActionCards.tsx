"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api-client";
import { AlertTriangle, Lightbulb, Zap, BarChart3, Check, X, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface ActionCard {
  id: string;
  card_type: "ALERT" | "SUGGESTION" | "WORKFLOW" | "REPORT";
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  module: number;
  title: string;
  insight: string;
  action: string;
  impact_estimate: string;
  requires_approval: boolean;
  auto_execute_action: string | null;
  meta: Record<string, unknown>;
}

interface CardsResponse {
  cards: ActionCard[];
  generated_at: string;
}

const CARD_STYLES: Record<string, {
  border: string; glow: string; badge: string; icon: React.ElementType; iconColor: string;
}> = {
  ALERT:      { border: "border-red-500/20",    glow: "bg-red-500/5",    badge: "bg-red-500/15 text-red-400 border-red-500/20",    icon: AlertTriangle, iconColor: "text-red-400"    },
  SUGGESTION: { border: "border-amber-500/20",  glow: "bg-amber-500/5",  badge: "bg-amber-500/15 text-amber-400 border-amber-500/20", icon: Lightbulb,     iconColor: "text-amber-400"  },
  WORKFLOW:   { border: "border-indigo-500/20", glow: "bg-indigo-500/5", badge: "bg-indigo-500/15 text-indigo-400 border-indigo-500/20", icon: Zap,        iconColor: "text-indigo-400" },
  REPORT:     { border: "border-white/10",      glow: "bg-white/[0.02]", badge: "bg-white/5 text-slate-400 border-white/10",        icon: BarChart3,     iconColor: "text-slate-400"  },
};

const PRIORITY_BADGE: Record<string, string> = {
  CRITICAL: "bg-red-600/80 text-white border-red-500/30",
  HIGH:     "bg-orange-600/70 text-white border-orange-500/30",
  MEDIUM:   "bg-yellow-600/60 text-white border-yellow-500/30",
  LOW:      "bg-white/10 text-slate-400 border-white/10",
};

const MODULE_LABELS: Record<number, string> = {
  1: "Inventory",
  2: "Pricing",
  3: "Workflow",
  5: "Customers",
};

export default function AiActionCards() {
  const [data, setData] = useState<CardsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [executing, setExecuting] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api.get<CardsResponse>("/api/ai/cards")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleApprove(card: ActionCard) {
    if (!card.auto_execute_action) {
      setDismissed((s) => new Set(s).add(card.id));
      toast.success("Action approved — complete it manually");
      return;
    }

    setExecuting(card.id);
    try {
      if (card.auto_execute_action === "send_reminder") {
        const res = await api.post<{ status: string; message: string }>(
          "/api/ai/actions/send-reminder",
          { invoice_id: card.meta.invoice_id }
        );
        toast.success(res.message);
      } else if (card.auto_execute_action === "draft_po") {
        const res = await api.post<{ status: string; message: string }>(
          "/api/ai/actions/draft-po",
          { product_id: card.meta.product_id, quantity: card.meta.suggested_qty ?? 20 }
        );
        toast.success(res.message);
      }
      setDismissed((s) => new Set(s).add(card.id));
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setExecuting(null);
    }
  }

  const visibleCards = data?.cards.filter((c) => !dismissed.has(c.id)) ?? [];
  const criticalCount = visibleCards.filter((c) => c.priority === "CRITICAL").length;

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2].map((i) => (
          <div key={i} className="h-20 skeleton rounded-xl" />
        ))}
      </div>
    );
  }

  if (visibleCards.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 text-[13px] font-semibold text-slate-300 hover:vf-text-1 transition-colors"
        >
          <Zap className="h-4 w-4 text-indigo-400" />
          AI Insights
          {criticalCount > 0 && (
            <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {criticalCount}
            </span>
          )}
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-slate-600" />
            : <ChevronDown className="h-3.5 w-3.5 text-slate-600" />}
        </button>
        <button
          onClick={load}
          className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-300 transition-colors"
        >
          <RefreshCw className="h-3 w-3" />Refresh
        </button>
      </div>

      {expanded && (
        <div className="space-y-2">
          {visibleCards.map((card) => {
            const style = CARD_STYLES[card.card_type] ?? CARD_STYLES.REPORT;
            const Icon = style.icon;
            const isExecuting = executing === card.id;

            return (
              <div
                key={card.id}
                className={cn(
                  "relative overflow-hidden rounded-xl border p-4 backdrop-blur-sm",
                  style.border, style.glow
                )}
              >
                {/* Subtle glow blob */}
                <div className="pointer-events-none absolute -top-8 -right-8 h-24 w-24 rounded-full bg-indigo-500/5 blur-2xl" />

                <div className="relative flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className={cn("mt-0.5 shrink-0 h-7 w-7 flex items-center justify-center rounded-lg bg-white/[0.04]")}>
                      <Icon className={cn("h-3.5 w-3.5", style.iconColor)} />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-bold", PRIORITY_BADGE[card.priority])}>
                          {card.priority}
                        </span>
                        <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-medium", style.badge)}>
                          {MODULE_LABELS[card.module] ?? `Module ${card.module}`}
                        </span>
                      </div>
                      <p className="text-[13px] font-semibold vf-text-1 leading-snug">{card.title}</p>
                      <p className="text-xs text-slate-500 leading-relaxed">{card.insight}</p>
                      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 mt-1">
                        <p className="text-xs font-medium text-slate-300">
                          <span className="text-slate-600 uppercase tracking-wide text-[10px] mr-1.5">Action</span>
                          {card.action}
                        </p>
                        <p className="text-[11px] text-slate-600 mt-0.5">{card.impact_estimate}</p>
                      </div>
                    </div>
                  </div>

                  {/* Buttons */}
                  <div className="flex shrink-0 flex-col gap-1.5">
                    <button
                      onClick={() => handleApprove(card)}
                      disabled={isExecuting}
                      className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
                    >
                      <Check className="h-3 w-3" />
                      {isExecuting ? "Running…" : card.requires_approval ? "Approve" : "Execute"}
                    </button>
                    <button
                      onClick={() => setDismissed((s) => new Set(s).add(card.id))}
                      className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-slate-500 hover:bg-white/[0.08] hover:text-slate-300 transition-colors"
                    >
                      <X className="h-3 w-3" />Dismiss
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
