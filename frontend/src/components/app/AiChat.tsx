"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import { Bot, Send, X, ChevronDown } from "lucide-react";

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
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch { return []; }
}

export default function AiChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(loadHistory());
  }, []);

  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30)));
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.post<{ reply: string }>("/api/integrations/ai/chat", { message: text });
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", content: `Error: ${e.message}` }]);
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
      {/* Floating button */}
      {!open && (
        <button
          suppressHydrationWarning
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-[#0f1724] text-white shadow-lg hover:bg-[#1a2840] transition-all hover:scale-105"
          title="Ask Varuflow AI"
        >
          <Bot className="h-5 w-5" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-40 flex flex-col w-80 sm:w-96 rounded-2xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between bg-[#0f1724] px-4 py-3">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-blue-300" />
              <span className="text-sm font-semibold text-white">Ask Varuflow</span>
              <span className="rounded-full bg-blue-500/20 px-1.5 py-0.5 text-[10px] text-blue-300">AI</span>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button onClick={clearHistory} className="rounded px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
                  Clear
                </button>
              )}
              <button onClick={() => setOpen(false)} className="rounded p-1 text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 max-h-80 bg-gray-50/50">
            {messages.length === 0 && (
              <div className="py-4 text-center">
                <p className="text-xs text-gray-400 mb-3">Ask anything about your business data</p>
                <div className="space-y-1.5">
                  {QUICK_PROMPTS.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-xs text-gray-600 hover:border-[#0f1724] hover:text-[#0f1724] transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`rounded-2xl px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-[#0f1724] text-white rounded-br-sm"
                    : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm"
                }`}>
                  {m.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="flex gap-1 rounded-2xl border border-gray-200 bg-white px-3 py-3 shadow-sm">
                  {[0,1,2].map(i => (
                    <span key={i} className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-100 p-3">
            <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your business…"
                disabled={loading}
                className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#0f1724] focus:outline-none focus:ring-1 focus:ring-[#0f1724] disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded-lg bg-[#0f1724] p-2 text-white hover:bg-[#1a2840] disabled:opacity-40 transition-colors"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
