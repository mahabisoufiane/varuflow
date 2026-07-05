"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Check, CircleDot, ArrowRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { toast } from "sonner";

interface HealthItem {
  key: string;
  label: string;
  done: boolean;
  weight: number;
  action_url: string | null;
}

interface SetupHealth {
  score: number;
  items: HealthItem[];
  next_steps: string[];
}

export default function SetupHealthPage() {
  const [health, setHealth] = useState<SetupHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const supabase = createClient();

  async function load() {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/auth/login"); return; }

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/onboarding/setup-health`,
        { headers: { Authorization: `Bearer ${session.access_token}` } },
      );
      if (res.status === 401) { router.push("/auth/login"); return; }
      if (!res.ok) {
        toast.error("Failed to load setup health");
        return;
      }
      setHealth(await res.json());
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const score = health?.score ?? 0;
  const scoreColor =
    score >= 80 ? "text-green-600" :
    score >= 50 ? "text-amber-600" :
                  "text-red-600";
  const barColor =
    score >= 80 ? "bg-green-500" :
    score >= 50 ? "bg-amber-400" :
                  "bg-red-400";

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Setup Health</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Track how completely your account is configured.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Score card */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-end justify-between mb-3">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Overall Score</p>
            <p className={`text-4xl font-bold ${scoreColor}`}>{score}<span className="text-xl text-muted-foreground">/100</span></p>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">
              {health ? `${health.items.filter((i) => i.done).length} / ${health.items.length} complete` : "—"}
            </p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-3 w-full rounded-full bg-gray-100 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${barColor}`}
            style={{ width: `${score}%` }}
          />
        </div>

        {score === 100 && (
          <p className="mt-3 text-sm text-green-600 font-medium flex items-center gap-1.5">
            <Check className="h-4 w-4" /> Your account is fully configured.
          </p>
        )}
      </div>

      {/* Items list */}
      <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
        {loading && !health
          ? Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-5 py-4 animate-pulse">
                <div className="h-5 w-5 rounded-full bg-gray-200 flex-shrink-0" />
                <div className="flex-1 h-4 rounded bg-gray-200" />
                <div className="h-3 w-16 rounded bg-gray-100" />
              </div>
            ))
          : health?.items.map((item) => (
              <div
                key={item.key}
                className={`flex items-center gap-3 px-5 py-4 ${item.done ? "" : "hover:bg-gray-50"} transition-colors`}
              >
                <div className={`flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full ${
                  item.done ? "bg-green-100" : "bg-gray-100"
                }`}>
                  {item.done
                    ? <Check className="h-3.5 w-3.5 text-green-600" />
                    : <CircleDot className="h-3.5 w-3.5 text-gray-400" />}
                </div>

                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${item.done ? "text-gray-500 line-through" : "text-gray-900"}`}>
                    {item.label}
                  </p>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-muted-foreground">{item.weight} pts</span>
                  {!item.done && item.action_url && (
                    <Link href={item.action_url}>
                      <Button variant="outline" size="sm" className="h-7 text-xs">
                        Fix <ArrowRight className="h-3 w-3 ml-1" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            ))}
      </div>

      {/* Next steps */}
      {health && health.next_steps.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 space-y-3">
          <p className="text-sm font-semibold text-amber-800">Recommended Next Steps</p>
          <ol className="space-y-2">
            {health.next_steps.map((key, idx) => {
              const item = health.items.find((i) => i.key === key);
              if (!item) return null;
              return (
                <li key={key} className="flex items-center gap-2.5 text-sm text-amber-900">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-200 text-xs font-semibold flex-shrink-0">
                    {idx + 1}
                  </span>
                  <span>{item.label}</span>
                  {item.action_url && (
                    <Link href={item.action_url} className="ml-auto text-amber-700 underline underline-offset-4 text-xs hover:text-amber-900">
                      Go →
                    </Link>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
