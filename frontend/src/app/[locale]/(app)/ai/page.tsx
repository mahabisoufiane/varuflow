"use client";

import { api } from "@/lib/api-client";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, BarChart3, Bot, Check, ChevronDown, ChevronUp,
  Lightbulb, RefreshCw, X, Zap,
} from "lucide-react";
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

const CARD_STYLES = {
  ALERT:      { border: "border-red-200",   bg: "bg-red-50",   badge: "bg-red-100 text-red-700",    icon: AlertTriangle },
  SUGGESTION: { border: "border-amber-200", bg: "bg-amber-50", badge: "bg-amber-100 text-amber-700", icon: Lightbulb },
  WORKFLOW:   { border: "border-blue-200",  bg: "bg-blue-50",  badge: "bg-blue-100 text-blue-700",   icon: Zap },
  REPORT:     { border: "border-gray-200",  bg: "bg-gray-50",  badge: "bg-gray-100 text-gray-700",   icon: BarChart3 },
} as const;

const PRIORITY_BADGE: Record<string, string> = {
  CRITICAL: "bg-red-600 text-white",
  HIGH:     "bg-orange-500 text-white",
  MEDIUM:   "bg-yellow-500 text-white",
  LOW:      "bg-gray-400 text-white",
};

const MODULE_LABELS: Record<number, { label: string; description: string }> = {
  1: { label: "Inventory Intelligence",    description: "Stockout risk, dead stock, purchase orders" },
  2: { label: "Margin Optimizer",          description: "Pricing gaps, margin leaks, bundle opportunities" },
  3: { label: "Automated Workflows",       description: "Cross-module anomaly detection and prescriptions" },
  5: { label: "Customer Intelligence",     description: "RFM segmentation, late payers, churn signals" },
};

function ModuleStatsBar({ cards, activeModule, onSelect }: {
  cards: ActionCard[];
  activeModule: number | null;
  onSelect: (m: number | null) => void;
}) {
  const modules = [1, 2, 3, 5];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {modules.map((m) => {
        const mCards = cards.filter((c) => c.module === m);
        const critical = mCards.filter((c) => c.priority === "CRITICAL").length;
        const info = MODULE_LABELS[m];
        const active = activeModule === m;
        return (
          <button
            key={m}
            onClick={() => onSelect(active ? null : m)}
            className={`rounded-xl border p-4 text-left transition-all ${
              active
                ? "border-[#1a2332] bg-[#1a2332] text-white"
                : "border-gray-200 bg-white hover:border-[#1a2332]/40"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className={`text-xs font-semibold uppercase tracking-wide ${active ? "text-blue-200" : "text-muted-foreground"}`}>
                Module {m}
              </span>
              {critical > 0 && (
                <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                  {critical}
                </span>
              )}
            </div>
            <p className={`text-sm font-bold leading-tight ${active ? "text-white" : "text-gray-900"}`}>
              {info.label}
            </p>
            <p className={`text-[11px] mt-1 ${active ? "text-blue-200" : "text-muted-foreground"}`}>
              {mCards.length} insight{mCards.length !== 1 ? "s" : ""}
            </p>
          </button>
        );
      })}
    </div>
  );
}

export default function AiAdvisorPage() {
  const [data, setData] = useState<CardsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [executing, setExecuting] = useState<string | null>(null);
  const [activeModule, setActiveModule] = useState<number | null>(null);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const load = useCallback(() => {
    setLoading(true);
    api.get<CardsResponse>("/api/ai/cards")
      .then(setData)
      .catch(() => toast.error("Failed to load AI insights"))
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

  function toggleExpand(id: string) {
    setExpandedCards((s) => {
      const next = new Set(s);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
  }

  const allCards = data?.cards.filter((c) => !dismissed.has(c.id)) ?? [];
  const visibleCards = activeModule ? allCards.filter((c) => c.module === activeModule) : allCards;

  const criticalCount = allCards.filter((c) => c.priority === "CRITICAL").length;
  const highCount = allCards.filter((c) => c.priority === "HIGH").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1a2332]">
              <Bot className="h-4 w-4 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-[#1a2332]">AI Advisor</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {loading ? "Analyzing your business data…" : (
              data
                ? `${allCards.length} insights · ${criticalCount} critical · generated ${new Date(data.generated_at).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" })}`
                : "Run analysis to see insights"
            )}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Analyzing…" : "Refresh"}
        </button>
      </div>

      {/* KPI summary row */}
      {!loading && allCards.length > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Critical", count: criticalCount, color: "bg-red-100 text-red-700 border-red-200" },
            { label: "High", count: highCount, color: "bg-orange-100 text-orange-700 border-orange-200" },
            { label: "Suggestions", count: allCards.filter((c) => c.card_type === "SUGGESTION").length, color: "bg-amber-100 text-amber-700 border-amber-200" },
            { label: "Total", count: allCards.length, color: "bg-gray-100 text-gray-700 border-gray-200" },
          ].map(({ label, count, color }) => (
            <div key={label} className={`rounded-xl border p-4 ${color}`}>
              <p className="text-2xl font-bold">{count}</p>
              <p className="text-xs font-medium mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Module filter */}
      {!loading && allCards.length > 0 && (
        <ModuleStatsBar
          cards={allCards}
          activeModule={activeModule}
          onSelect={setActiveModule}
        />
      )}

      {/* Cards */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-gray-100" />
          ))}
        </div>
      ) : visibleCards.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center">
          <Bot className="mx-auto h-10 w-10 text-gray-300 mb-3" />
          <p className="font-semibold text-gray-900">
            {allCards.length === 0 ? "All clear — no issues detected" : "No insights in this module"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {allCards.length === 0
              ? "Your inventory, invoices, and customers all look healthy."
              : "Try another module or refresh to re-run the analysis."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleCards.map((card) => {
            const style = CARD_STYLES[card.card_type];
            const Icon = style.icon;
            const isExecuting = executing === card.id;
            const isExpanded = expandedCards.has(card.id);

            return (
              <div
                key={card.id}
                className={`rounded-xl border ${style.border} ${style.bg} overflow-hidden`}
              >
                {/* Card header — always visible */}
                <div className="flex items-start gap-3 p-4">
                  <Icon className="h-4 w-4 mt-0.5 shrink-0 text-gray-600" />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${PRIORITY_BADGE[card.priority]}`}>
                        {card.priority}
                      </span>
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}>
                        {MODULE_LABELS[card.module]?.label ?? `Module ${card.module}`}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-gray-900 leading-snug">{card.title}</p>
                  </div>

                  {/* Expand + action buttons */}
                  <div className="flex shrink-0 items-center gap-1.5">
                    <button
                      onClick={() => toggleExpand(card.id)}
                      className="rounded p-1 text-gray-400 hover:bg-white/60 hover:text-gray-700"
                    >
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                    <button
                      onClick={() => handleApprove(card)}
                      disabled={isExecuting}
                      className="inline-flex items-center gap-1 rounded-lg bg-[#1a2332] px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-[#2a3342] disabled:opacity-60 transition-colors"
                    >
                      <Check className="h-3 w-3" />
                      {isExecuting ? "Running…" : card.auto_execute_action ? "Execute" : "Approve"}
                    </button>
                    <button
                      onClick={() => setDismissed((s) => new Set(s).add(card.id))}
                      className="rounded p-1.5 text-gray-400 hover:bg-white/60 hover:text-red-500"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-white/50 bg-white/40 px-4 py-3 space-y-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">Insight</p>
                      <p className="text-sm text-gray-700 leading-relaxed">{card.insight}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg bg-white border border-white p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">Recommended Action</p>
                        <p className="text-sm font-medium text-gray-800">{card.action}</p>
                      </div>
                      <div className="rounded-lg bg-white border border-white p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">Business Impact</p>
                        <p className="text-sm font-medium text-gray-800">{card.impact_estimate}</p>
                      </div>
                    </div>
                    {card.requires_approval && (
                      <p className="text-[11px] text-gray-500">
                        🔐 Requires approval before execution
                        {card.auto_execute_action
                          ? ` — will auto-run: ${card.auto_execute_action.replace("_", " ")}`
                          : ""}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
