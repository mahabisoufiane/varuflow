"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Wrench, ChevronUp, ChevronDown } from "lucide-react";

const PLANS = [
  { key: "FREE",       label: "FREE",       color: "bg-slate-500" },
  { key: "PRO",        label: "PRO",        color: "bg-indigo-500" },
  { key: "ENTERPRISE", label: "ENTERPRISE", color: "bg-amber-500"  },
] as const;

/**
 * Dev-only floating toolbar for quickly switching org plan + seeing current state.
 * Only rendered when NODE_ENV=development. In production this component is a no-op.
 */
export function DevToolbar() {
  const [plan, setPlan]       = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen]       = useState(true);
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => {
    api.get<{ role: string; organization: { plan: string } }>("/api/auth/me")
      .then((me) => { setPlan(me.organization.plan); setApiDown(false); })
      .catch(() => { setApiDown(true); });
  }, []);

  async function switchPlan(newPlan: string) {
    if (loading || newPlan === plan) return;
    setLoading(true);
    try {
      await api.post("/api/dev/set-plan", { plan: newPlan });
      setPlan(newPlan);
      toast.success(`Plan switched to ${newPlan} — reloading…`);
      setTimeout(() => window.location.reload(), 800);
    } catch (e: unknown) {
      toast.error((e as Error).message ?? "Failed to switch plan");
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed bottom-0 left-1/2 z-[9999] -translate-x-1/2"
      style={{ fontFamily: "ui-monospace, monospace" }}>
      <div
        className="flex items-center gap-0 rounded-t-xl overflow-hidden shadow-2xl"
        style={{ background: "#18181b", border: "1px solid #3f3f46", borderBottom: "none" }}>

        {/* Toggle collapse */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-2 text-[11px] font-bold text-zinc-400 hover:text-white transition-colors"
          title="Toggle dev toolbar">
          <Wrench className="h-3 w-3" />
          DEV
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
        </button>

        {open && (
          <>
            <div className="w-px h-6 bg-zinc-700" />

            {/* Plan label */}
            <span className="px-3 text-[11px] text-zinc-500">Plan:</span>
            {apiDown ? (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold text-red-400 bg-red-500/20 mr-2">
                API DOWN
              </span>
            ) : (
              <span className={cn(
                "px-2 py-0.5 rounded text-[10px] font-bold text-white mr-2",
                plan === "FREE" ? "bg-slate-600" : plan === "PRO" ? "bg-indigo-600" : "bg-amber-600"
              )}>
                {plan ?? "…"}
              </span>
            )}

            <div className="w-px h-6 bg-zinc-700" />

            {/* Plan switcher buttons */}
            {PLANS.map(({ key, label, color }) => (
              <button
                key={key}
                onClick={() => switchPlan(key)}
                disabled={loading || plan === key}
                className={cn(
                  "px-3 py-2 text-[11px] font-semibold transition-all",
                  plan === key
                    ? `${color} text-white cursor-default`
                    : "text-zinc-400 hover:text-white hover:bg-zinc-800",
                  (loading || plan === key) && "opacity-60 cursor-not-allowed"
                )}>
                {label}
              </button>
            ))}

            <div className="w-px h-6 bg-zinc-700" />

            {/* Quick navigation */}
            <span className="px-3 text-[11px] text-zinc-500">Go to:</span>
            {[
              { label: "Dashboard",  href: "/en/dashboard" },
              { label: "Register",   href: "/en/register"  },
              { label: "Settings",   href: "/en/settings"  },
              { label: "Multi-Org",  href: "/en/multi-entity" },
            ].map(({ label, href }) => (
              <a
                key={href}
                href={href}
                className="px-3 py-2 text-[11px] text-zinc-400 hover:text-white transition-colors">
                {label}
              </a>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
