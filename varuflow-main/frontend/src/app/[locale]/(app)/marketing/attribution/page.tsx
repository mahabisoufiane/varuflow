"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface AttributionSummaryRow {
  channel: string;
  leads: number;
  conversions: number;
  revenue: number;
  conversion_rate: number;
}

interface FunnelData {
  leads: number;
  conversions: number;
  purchases: number;
}

interface AttributionSource {
  id: string;
  name: string;
  channel: string;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
}

const CHANNEL_COLORS: Record<string, string> = {
  google_ads: "bg-yellow-100 text-yellow-700",
  referral: "bg-purple-100 text-purple-700",
  organic: "bg-green-100 text-green-700",
  social: "bg-blue-100 text-blue-700",
  email: "bg-orange-100 text-orange-700",
  other: "bg-gray-100 text-gray-600",
};

const CHANNEL_MODULE: Record<string, keyof typeof styles> = {
  google_ads: "channelGoogleAds",
  referral:   "channelReferral",
  organic:    "channelOrganic",
  social:     "channelSocial",
  email:      "channelEmail",
  other:      "channelOther",
};

export default function AttributionPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [summary, setSummary] = useState<AttributionSummaryRow[]>([]);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [sources, setSources] = useState<AttributionSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [showSourceForm, setShowSourceForm] = useState(false);
  const [sourceForm, setSourceForm] = useState({ name: "", channel: "organic", utm_source: "", utm_medium: "", utm_campaign: "" });

  const [showEventModal, setShowEventModal] = useState(false);
  const [eventForm, setEventForm] = useState({ source_id: "", event_type: "lead", channel: "organic", revenue: "" });

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const headers = { Authorization: `Bearer ${token}` };
      const params = new URLSearchParams();
      if (dateFrom) params.set("from", dateFrom);
      if (dateTo) params.set("to", dateTo);
      const qs = params.toString() ? "?" + params.toString() : "";
      const [sumRes, funnelRes, srcRes] = await Promise.all([
        fetch(apiUrl(`/api/attribution/summary${qs}`), { headers }),
        fetch(apiUrl("/api/attribution/funnel"), { headers }),
        fetch(apiUrl("/api/attribution/sources"), { headers }),
      ]);
      if (sumRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (sumRes.ok) {
        const data: AttributionSummaryRow[] = await sumRes.json();
        setSummary(data.sort((a, b) => b.revenue - a.revenue));
      }
      if (funnelRes.ok) setFunnel(await funnelRes.json());
      if (srcRes.ok) setSources(await srcRes.json());
    } catch {
      toast.error("Failed to load attribution data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createSource() {
    if (!sourceForm.name.trim()) { toast.error("Name is required"); return; }
    setActionLoading("src_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/attribution/sources"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: sourceForm.name,
          channel: sourceForm.channel,
          utm_source: sourceForm.utm_source || null,
          utm_medium: sourceForm.utm_medium || null,
          utm_campaign: sourceForm.utm_campaign || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Source created");
      setShowSourceForm(false);
      setSourceForm({ name: "", channel: "organic", utm_source: "", utm_medium: "", utm_campaign: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function deleteSource(id: string) {
    setActionLoading(id + "_del");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/attribution/sources/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to delete"); return; }
      toast.success("Source deleted");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function logEvent() {
    if (!eventForm.source_id || !eventForm.event_type) { toast.error("Source and event type are required"); return; }
    setActionLoading("event_log");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/attribution/events"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          source_id: eventForm.source_id,
          event_type: eventForm.event_type,
          channel: eventForm.channel,
          revenue: eventForm.revenue ? parseFloat(eventForm.revenue) : null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to log event"); return; }
      toast.success("Event logged");
      setShowEventModal(false);
      setEventForm({ source_id: "", event_type: "lead", channel: "organic", revenue: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Marketing Attribution</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Track which channels bring the highest LTV customers.</p>
        </div>
        <Button onClick={() => setShowEventModal(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Log Event
        </Button>
      </div>

      {/* Date filter */}
      <div className="flex items-center gap-3">
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
        <span className="text-sm text-gray-500">to</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
        <Button variant="outline" size="sm" onClick={load}>Apply</Button>
      </div>

      {loading ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <>
          {/* Summary table */}
          <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">Channel</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">Leads</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">Conversions</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">Revenue (SEK)</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">Conv. Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {summary.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500">No data yet</td></tr>
                ) : summary.map((row) => (
                  <tr key={row.channel}>
                    <td className="px-4 py-3">
                      <span className={styles[CHANNEL_MODULE[row.channel] ?? "channelOther"]}>
                        {row.channel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.leads?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.conversions?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.revenue?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.conversion_rate?.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Funnel */}
          {funnel && (
            <div className="rounded-xl border bg-white shadow-sm p-5">
              <p className="text-sm font-semibold text-gray-900 mb-4">Conversion Funnel</p>
              <div className="grid grid-cols-3 gap-4 text-center">
                {[
                  { label: "Leads", value: funnel.leads, color: "bg-blue-50 text-blue-700" },
                  { label: "Conversions", value: funnel.conversions, color: "bg-green-50 text-green-700" },
                  { label: "Purchases", value: funnel.purchases, color: "bg-purple-50 text-purple-700" },
                ].map(({ label, value, color }) => (
                  <div key={label} className={`rounded-lg p-4 ${color}`}>
                    <p className="text-2xl font-bold">{value?.toLocaleString()}</p>
                    <p className="text-sm mt-1">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sources */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-900">Attribution Sources</p>
              <Button size="sm" onClick={() => setShowSourceForm(true)}
                className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
                <PlusCircle className="h-3 w-3" /> Add Source
              </Button>
            </div>
            {showSourceForm && (
              <div className="rounded-xl border border-[#1a2332]/20 bg-white p-4 shadow-sm space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-gray-700">Name *</label>
                    <input value={sourceForm.name} onChange={(e) => setSourceForm((f) => ({ ...f, name: e.target.value }))}
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-gray-700">Channel</label>
                    <select value={sourceForm.channel} onChange={(e) => setSourceForm((f) => ({ ...f, channel: e.target.value }))}
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                      {["google_ads", "referral", "organic", "social", "email", "other"].map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  {[
                    { key: "utm_source" as const, label: "UTM Source" },
                    { key: "utm_medium" as const, label: "UTM Medium" },
                    { key: "utm_campaign" as const, label: "UTM Campaign" },
                  ].map(({ key, label }) => (
                    <div key={key} className="space-y-1">
                      <label className="text-xs font-medium text-gray-700">{label}</label>
                      <input value={sourceForm[key]} onChange={(e) => setSourceForm((f) => ({ ...f, [key]: e.target.value }))}
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setShowSourceForm(false)}>Cancel</Button>
                  <Button size="sm" disabled={actionLoading === "src_create"} onClick={createSource}
                    className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                    {actionLoading === "src_create" ? "Creating…" : "Add Source"}
                  </Button>
                </div>
              </div>
            )}
            <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
              {sources.length === 0 ? (
                <div className="py-8 text-center text-sm text-gray-500">No sources yet</div>
              ) : sources.map((s) => (
                <div key={s.id} className="flex items-center gap-4 px-5 py-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">{s.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {[s.utm_source, s.utm_medium, s.utm_campaign].filter(Boolean).join(" / ")}
                    </p>
                  </div>
                  <span className={styles[CHANNEL_MODULE[s.channel] ?? "channelOther"]}>
                    {s.channel}
                  </span>
                  <button type="button" disabled={actionLoading === s.id + "_del"}
                    onClick={() => deleteSource(s.id)}
                    className="text-red-400 hover:text-red-600 disabled:opacity-50">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Log Event modal */}
      {showEventModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-gray-900">Log Attribution Event</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Source *</label>
                <select value={eventForm.source_id} onChange={(e) => setEventForm((f) => ({ ...f, source_id: e.target.value }))}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                  <option value="">Select source…</option>
                  {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Event Type</label>
                  <select value={eventForm.event_type} onChange={(e) => setEventForm((f) => ({ ...f, event_type: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                    {["lead", "conversion", "purchase"].map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Channel</label>
                  <select value={eventForm.channel} onChange={(e) => setEventForm((f) => ({ ...f, channel: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                    {["google_ads", "referral", "organic", "social", "email", "other"].map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Revenue (optional)</label>
                  <input type="number" value={eventForm.revenue} onChange={(e) => setEventForm((f) => ({ ...f, revenue: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowEventModal(false)}>Cancel</Button>
              <Button disabled={actionLoading === "event_log"} onClick={logEvent}
                className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {actionLoading === "event_log" ? "Logging…" : "Log Event"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
