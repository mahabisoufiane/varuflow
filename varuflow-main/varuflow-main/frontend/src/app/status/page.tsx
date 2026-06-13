"use client";

/**
 * Public Varuflow status page.
 *
 * Lives outside `[locale]` because operational status pages should be
 * stable, single-language (English) URLs that on-call engineers and
 * uptime monitors can bookmark. No auth, no Supabase client, no
 * tenant context. Plain `fetch` against the backend with a 60-second
 * polling cadence so a visitor watching the page sees fresh data
 * without an aggressive refresh loop.
 */

import { useEffect, useState } from "react";

interface ServiceTimelinePoint {
  date: string;
  uptime_pct: number | null;
}

interface ServiceRollup {
  key: "api" | "database" | "payments" | "email";
  uptime_pct_90d: number | null;
  timeline: ServiceTimelinePoint[];
}

interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: "minor" | "major" | "critical";
  started_at: string;
  resolved_at: string | null;
}

interface StatusPayload {
  overall: "operational" | "degraded" | "outage" | "unknown";
  checked_at: string | null;
  services: ServiceRollup[];
  incidents: Incident[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const REFRESH_MS = 60_000;

const SERVICE_LABELS: Record<ServiceRollup["key"], string> = {
  api: "API",
  database: "Database",
  payments: "Payments",
  email: "Email",
};

function overallBadge(overall: StatusPayload["overall"]) {
  switch (overall) {
    case "operational":
      return { text: "All systems operational", tone: "bg-emerald-500" };
    case "degraded":
      return { text: "Degraded performance", tone: "bg-amber-500" };
    case "outage":
      return { text: "Major outage", tone: "bg-red-600" };
    default:
      return { text: "Status unknown", tone: "bg-gray-400" };
  }
}

function dotColor(uptime: number | null): string {
  if (uptime === null) return "bg-gray-200"; // no probe that day
  if (uptime >= 99.5) return "bg-emerald-500";
  if (uptime >= 95) return "bg-amber-500";
  return "bg-red-600";
}

export default function StatusPage() {
  const [data, setData] = useState<StatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/health/status-history`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = (await res.json()) as StatusPayload;
        if (!cancelled) {
          setData(json);
          setError(null);
          setLastFetched(new Date());
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }

    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const badge = overallBadge(data?.overall ?? "unknown");

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <header className="mb-10">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            Varuflow
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">System status</h1>
          <p className="mt-1 text-sm text-gray-500">
            Live availability of Varuflow services. Updated every 60 seconds.
          </p>
        </header>

        {/* Overall status badge */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex h-3 w-3 animate-pulse rounded-full ${badge.tone}`}
              aria-hidden
            />
            <p className="text-lg font-semibold">{badge.text}</p>
          </div>
          {data?.checked_at && (
            <p className="mt-2 text-xs text-gray-400">
              Last checked {new Date(data.checked_at).toLocaleString("en-GB")}
            </p>
          )}
          {error && (
            <p className="mt-2 text-xs text-red-500">
              Could not reach status API: {error}
            </p>
          )}
        </div>

        {/* Per-service uptime rows */}
        <section className="mt-10 space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
            90-day uptime
          </h2>
          <div className="divide-y divide-gray-100 rounded-2xl border border-gray-200 bg-white shadow-sm">
            {(data?.services ?? []).map((svc) => (
              <div key={svc.key} className="px-6 py-5">
                <div className="flex items-baseline justify-between">
                  <p className="font-semibold">{SERVICE_LABELS[svc.key]}</p>
                  <p className="text-sm tabular-nums text-gray-500">
                    {svc.uptime_pct_90d === null
                      ? "—"
                      : `${svc.uptime_pct_90d.toFixed(2)}%`}
                  </p>
                </div>
                {/* Stripe-style 90-dot bar — newest day on the right. */}
                <div className="mt-3 flex gap-[2px]" aria-label={`${svc.key} timeline`}>
                  {svc.timeline.map((pt) => (
                    <span
                      key={pt.date}
                      title={`${pt.date}: ${pt.uptime_pct === null ? "no data" : pt.uptime_pct + "%"}`}
                      className={`h-6 flex-1 rounded-sm ${dotColor(pt.uptime_pct)}`}
                    />
                  ))}
                </div>
              </div>
            ))}
            {!data && (
              <div className="px-6 py-12 text-center text-sm text-gray-400">
                Loading…
              </div>
            )}
          </div>
        </section>

        {/* Incidents */}
        <section className="mt-10">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
            Recent incidents
          </h2>
          <div className="mt-3 rounded-2xl border border-gray-200 bg-white shadow-sm">
            {data?.incidents && data.incidents.length > 0 ? (
              <ul className="divide-y divide-gray-100">
                {data.incidents.map((inc) => (
                  <li key={inc.id} className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex h-2 w-2 rounded-full ${
                          inc.severity === "critical"
                            ? "bg-red-600"
                            : inc.severity === "major"
                            ? "bg-amber-500"
                            : "bg-yellow-400"
                        }`}
                        aria-hidden
                      />
                      <p className="font-medium">{inc.title}</p>
                      {inc.resolved_at && (
                        <span className="ml-auto text-xs text-emerald-600">
                          Resolved
                        </span>
                      )}
                    </div>
                    {inc.description && (
                      <p className="mt-1 text-sm text-gray-600">{inc.description}</p>
                    )}
                    <p className="mt-1 text-xs text-gray-400">
                      {new Date(inc.started_at).toLocaleString("en-GB")}
                      {inc.resolved_at &&
                        ` — resolved ${new Date(inc.resolved_at).toLocaleString("en-GB")}`}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-6 py-8 text-center text-sm text-gray-400">
                No incidents reported.
              </p>
            )}
          </div>
        </section>

        <footer className="mt-12 text-center text-xs text-gray-400">
          {lastFetched && (
            <>Refreshed {lastFetched.toLocaleTimeString("en-GB")} · auto-refresh every 60 s</>
          )}
        </footer>
      </div>
    </main>
  );
}
