"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api-client";
import { AlertTriangle, Lightbulb, Zap, BarChart3, Check, X, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";

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

const CARD_STYLES: Record<string, { border: string; bg: string; badge: string; icon: React.ElementType }> = {
  ALERT:      { border: "border-red-200",    bg: "bg-red-50",    badge: "bg-red-100 text-red-700",    icon: AlertTriangle },
  SUGGESTION: { border: "border-amber-200",  bg: "bg-amber-50",  badge: "bg-amber-100 text-amber-700", icon: Lightbulb },
  WORKFLOW:   { border: "border-blue-200",   bg: "bg-blue-50",   badge: "bg-blue-100 text-blue-700",   icon: Zap },
  REPORT:     { border: "border-gray-200",   bg: "bg-gray-50",   badge: "bg-gray-100 text-gray-700",   icon: BarChart3 },
};

const PRIORITY_BADGE: Record<string, string> = {
  CRITICAL: "bg-red-600 text-white",
  HIGH:     "bg-orange-500 text-white",
  MEDIUM:   "bg-yellow-500 text-white",
  LOW:      "bg-gray-400 text-white",
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
    } catch (e: any) {
      toast.error(e.message);
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
          <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-100" />
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
          className="flex items-center gap-2 text-sm font-semibold text-gray-900"
        >
          <Zap className="h-4 w-4 text-blue-500" />
          AI Insights
          {criticalCount > 0 && (
            <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {criticalCount}
            </span>
          )}
          {expanded ? <ChevronUp className="h-3.5 w-3.5 text-gray-400" /> : <ChevronDown className="h-3.5 w-3.5 text-gray-400" />}
        </button>
        <button
          onClick={load}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-gray-900"
        >
          <RefreshCw className="h-3 w-3" />Refresh
        </button>
      </div>

      {expanded && (
        <div className="space-y-2">
          {visibleCards.map((card) => {
            const style = CARD_STYLES[card.card_type] ?? CARD_STYLES.ALERT;
            const Icon = style.icon;
            const isExecuting = executing === card.id;

            return (
              <div
                key={card.id}
                className={`rounded-xl border ${style.border} ${style.bg} p-4`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <Icon className="h-4 w-4 mt-0.5 shrink-0 text-gray-600" />
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${PRIORITY_BADGE[card.priority]}`}>
                          {card.priority}
                        </span>
                        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}>
                          {MODULE_LABELS[card.module] ?? `Module ${card.module}`}
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-gray-900 leading-snug">{card.title}</p>
                      <p className="text-xs text-gray-600 leading-relaxed">{card.insight}</p>
                      <div className="rounded-lg border border-white/60 bg-white/50 px-3 py-2 mt-2">
                        <p className="text-xs font-medium text-gray-700">
                          <span className="text-gray-400 uppercase tracking-wide text-[10px] mr-1">Action</span>
                          {card.action}
                        </p>
                        <p className="text-[11px] text-gray-500 mt-0.5">{card.impact_estimate}</p>
                      </div>
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="flex shrink-0 flex-col gap-1.5">
                    <button
                      onClick={() => handleApprove(card)}
                      disabled={isExecuting}
                      className="inline-flex items-center gap-1 rounded-lg bg-[#1a2332] px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-[#2a3342] disabled:opacity-60 transition-colors"
                    >
                      <Check className="h-3 w-3" />
                      {isExecuting ? "Running…" : card.requires_approval ? "Approve" : "Execute"}
                    </button>
                    <button
                      onClick={() => setDismissed((s) => new Set(s).add(card.id))}
                      className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-gray-500 hover:bg-gray-50 transition-colors"
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
