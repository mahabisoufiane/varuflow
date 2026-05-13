"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import { Bot, Send, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const QUICK_PROMPTS = [
  "Which invoices are overdue and need follow-up?",
  "What products are at stockout risk this week?",
  "Which customers haven't ordered in 45+ days?",
  "Which products have the worst profit margins?",
  "Summarize my cash flow situation",
  "Who are my top 5 customers by revenue?",
];

const STORAGE_KEY = "varuflow_ai_history";

function loadHistory(): Message[] {
  // Validate the shape before trusting localStorage — a malformed entry
  // (e.g. user edited storage, or an older version's schema) must not
  // crash the component or feed non-strings into `content` where later
  // rendering logic expects `.length`, `.split()`, etc.
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (m): m is Message =>
        m &&
        typeof m === "object" &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.content === "string"
    );
  } catch {
    return [];
  }
}

interface AiContextSnapshot {
  low_stock_count: number;
  top_low_stock_names: string[];
  revenue_30d_sek: number;
  overdue_count: number;
  month_delta_pct: number | null;
}

export default function AiChat() {
  const [open, setOpen]       = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [ctx, setCtx]         = useState<AiContextSnapshot | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setMessages(loadHistory()); }, []);

  // Fetch the live business snapshot once when the panel opens so the
  // chips reflect the current cash-flow/inventory state. Silent-fail on
  // FREE users (403 from require_plan) — the chat panel still works.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api.get<AiContextSnapshot>("/api/integrations/ai/context")
      .then((data) => { if (!cancelled) setCtx(data); })
      .catch(() => { if (!cancelled) setCtx(null); });
    return () => { cancelled = true; };
  }, [open]);

  useEffect(() => {
    if (messages.length > 0) {
      // Wrap in try/catch so a QuotaExceededError (Safari private mode,
      // full storage) doesn't crash the chat component.
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30)));
      } catch {}
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.post<{ reply: string }>("/api/integrations/ai/chat", { message: text });
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (e: unknown) {
      setMessages((m) => [...m, { role: "assistant", content: `Error: ${(e as Error).message}` }]);
    } finally {
      setLoading(false);
    }
  }

  function clearHistory() {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <>
      {/* Floating button — hidden on mobile (bottom nav covers it) */}
      {!open && (
        <button
          suppressHydrationWarning
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 hidden lg:flex h-12 w-12 items-center justify-center rounded-full bg-indigo-600 text-white shadow-glow hover:bg-indigo-500 transition-all hover:scale-105"
          title="Ask Varuflow AI"
        >
          <Bot className="h-5 w-5" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col w-80 sm:w-96 rounded-2xl border border-white/[0.08] bg-vf-surface shadow-elevated overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 bg-vf-elevated">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600">
                <Bot className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-[13px] font-semibold vf-text-1">Ask Varuflow</span>
              <span className="rounded-full bg-indigo-500/20 border border-indigo-500/20 px-1.5 py-0.5 text-[10px] text-indigo-400">AI</span>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button onClick={clearHistory}
                  className="rounded px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-300 hover:bg-white/5 transition-colors">
                  Clear
                </button>
              )}
              <button onClick={() => setOpen(false)}
                className="rounded p-1 text-slate-600 hover:text-slate-300 hover:bg-white/5 transition-colors">
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 max-h-80">
            {messages.length === 0 && (
              <div className="py-4 text-center">
                <p className="text-xs text-slate-600 mb-3">Ask anything about your business data</p>
                <div className="space-y-1.5">
                  {QUICK_PROMPTS.map((q) => (
                    <button key={q} onClick={() => send(q)}
                      className="block w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-left text-xs text-slate-500 hover:border-indigo-500/30 hover:bg-indigo-500/5 hover:text-slate-300 transition-colors">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn(
                  "rounded-2xl px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap",
                  m.role === "user"
                    ? "bg-indigo-600 text-white rounded-br-sm"
                    : "bg-vf-elevated border border-white/[0.06] text-slate-300 rounded-bl-sm"
                )}>
                  {m.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="flex gap-1 rounded-2xl border border-white/[0.06] bg-vf-elevated px-3 py-3">
                  {[0,1,2].map(i => (
                    <span key={i} className="h-1.5 w-1.5 rounded-full bg-slate-500 animate-bounce-dot"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-white/[0.06] p-3">
            {ctx && (ctx.low_stock_count > 0 || ctx.month_delta_pct !== null || ctx.overdue_count > 0) && (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {ctx.low_stock_count > 0 && (
                  <button
                    type="button"
                    onClick={() => send(
                      `Vilka ${ctx.low_stock_count} produkter är snart slut i lager och vad ska jag göra?`
                    )}
                    disabled={loading}
                    title={ctx.top_low_stock_names.join(", ")}
                    className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-300 hover:bg-amber-500/20 disabled:opacity-50 transition-colors"
                  >
                    📦 {ctx.low_stock_count} produkter snart slut
                  </button>
                )}
                {ctx.month_delta_pct !== null && (
                  <button
                    type="button"
                    onClick={() => send(
                      ctx.month_delta_pct! >= 0
                        ? "Varför har försäljningen gått upp jämfört med förra månaden?"
                        : "Varför har försäljningen gått ner jämfört med förra månaden?"
                    )}
                    disabled={loading}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-50",
                      ctx.month_delta_pct >= 0
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                        : "border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20"
                    )}
                  >
                    💰 {ctx.month_delta_pct >= 0 ? "+" : ""}{ctx.month_delta_pct.toFixed(0)}% vs förra månaden
                  </button>
                )}
                {ctx.overdue_count > 0 && (
                  <button
                    type="button"
                    onClick={() => send(
                      `Vilka ${ctx.overdue_count} fakturor är mest förfallna och hur ska jag prioritera dem?`
                    )}
                    disabled={loading}
                    className="rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[11px] font-medium text-red-300 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
                  >
                    ⚠️ {ctx.overdue_count} förfallna fakturor
                  </button>
                )}
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your business…"
                disabled={loading}
                className="vf-input flex-1 text-xs py-2 px-3 h-auto disabled:opacity-50"
              />
              <button type="submit" disabled={loading || !input.trim()}
                className="rounded-lg bg-indigo-600 p-2 text-white hover:bg-indigo-500 disabled:opacity-40 transition-colors">
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
