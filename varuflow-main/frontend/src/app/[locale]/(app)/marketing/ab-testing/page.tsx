"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface Variant {
  id: string;
  label: string;
  subject_line: string | null;
  body_html: string | null;
  recipient_pct: number | null;
  sent: number;
  opens: number;
  clicks: number;
  conversions: number;
}

interface ABTest {
  id: string;
  name: string;
  test_metric: string;
  status: "draft" | "running" | "complete";
  winner_variant: string | null;
  auto_promote: boolean;
  variants: Variant[];
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700",
  complete: "bg-green-100 text-green-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:    "statusDraft",
  running:  "statusRunning",
  complete: "statusComplete",
};

export default function ABTestingPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [tests, setTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ name: "", test_metric: "open_rate", auto_promote: true });

  const [variantEdits, setVariantEdits] = useState<Record<string, { subject_line: string; body_html: string; recipient_pct: string }>>({});
  const [statsModal, setStatsModal] = useState<{ testId: string; variantId: string; sent: string; opens: string; clicks: string; conversions: string } | null>(null);

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
      const res = await fetch(apiUrl("/api/ab-testing"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) {
        const data: ABTest[] = await res.json();
        setTests(data);
        const ve: typeof variantEdits = {};
        data.forEach((t) => {
          t.variants?.forEach((v) => {
            ve[v.id] = { subject_line: v.subject_line ?? "", body_html: v.body_html ?? "", recipient_pct: String(v.recipient_pct ?? "") };
          });
        });
        setVariantEdits(ve);
      }
    } catch {
      toast.error("Failed to load A/B tests");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createTest() {
    if (!newForm.name.trim()) { toast.error("Name is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/ab-testing"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(newForm),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Test created");
      setShowNew(false);
      setNewForm({ name: "", test_metric: "open_rate", auto_promote: true });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function saveVariant(testId: string, variantId: string) {
    const ve = variantEdits[variantId];
    if (!ve) return;
    setActionLoading(variantId + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/ab-testing/${testId}/variants/${variantId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          subject_line: ve.subject_line || null,
          body_html: ve.body_html || null,
          recipient_pct: ve.recipient_pct ? parseFloat(ve.recipient_pct) : null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to save"); return; }
      toast.success("Variant saved");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function startTest(id: string) {
    setActionLoading(id + "_start");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/ab-testing/${id}/start`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to start"); return; }
      toast.success("Test started");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function completeTest(id: string) {
    setActionLoading(id + "_complete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/ab-testing/${id}/complete`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed"); return; }
      const data = await res.json();
      toast.success(`Winner: Variant ${data.winner_variant ?? "—"}`);
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function recordStats() {
    if (!statsModal) return;
    setActionLoading("stats_record");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/ab-testing/${statsModal.testId}/record`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          variant_id: statsModal.variantId,
          sent: parseInt(statsModal.sent) || 0,
          opens: parseInt(statsModal.opens) || 0,
          clicks: parseInt(statsModal.clicks) || 0,
          conversions: parseInt(statsModal.conversions) || 0,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed"); return; }
      toast.success("Stats recorded");
      setStatsModal(null);
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Email A/B Testing</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Test campaign variants and auto-promote winners.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Test
        </Button>
      </div>

      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create A/B Test</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-gray-700">Name *</label>
              <input value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Black Friday Subject Line Test"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Test Metric</label>
              <select value={newForm.test_metric} onChange={(e) => setNewForm((f) => ({ ...f, test_metric: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                {["open_rate", "click_rate", "conversion_rate"].map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2 pt-5">
              <input type="checkbox" id="auto_promote" checked={newForm.auto_promote}
                onChange={(e) => setNewForm((f) => ({ ...f, auto_promote: e.target.checked }))} />
              <label htmlFor="auto_promote" className="text-sm text-gray-700">Auto-promote winner</label>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createTest}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Test"}
            </Button>
          </div>
        </div>
      )}

      {loading && tests.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {tests.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-500">No A/B tests yet</div>
          ) : tests.map((t) => {
            const expanded = expandedId === t.id;
            return (
              <div key={t.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setExpandedId(expanded ? null : t.id)}>
                    <p className="text-sm font-medium text-gray-900">{t.name}</p>
                    <p className="text-xs text-muted-foreground">{t.test_metric}</p>
                    {t.status === "complete" && t.winner_variant && (
                      <p className="text-xs text-green-600 mt-0.5 font-medium">Winner: {t.winner_variant}</p>
                    )}
                  </div>
                  <span className={styles[STATUS_MODULE[t.status] ?? "statusDraft"]}>
                    {t.status}
                  </span>
                  <div className="flex items-center gap-2">
                    {t.status === "draft" && (
                      <Button size="sm" disabled={actionLoading === t.id + "_start"} onClick={() => startTest(t.id)}
                        className="bg-blue-600 hover:bg-blue-700 text-white">
                        Start Test
                      </Button>
                    )}
                    {t.status === "running" && (
                      <>
                        <Button size="sm" variant="outline"
                          onClick={() => setStatsModal({ testId: t.id, variantId: t.variants?.[0]?.id ?? "", sent: "", opens: "", clicks: "", conversions: "" })}>
                          Record Stats
                        </Button>
                        <Button size="sm" disabled={actionLoading === t.id + "_complete"} onClick={() => completeTest(t.id)}
                          className="bg-green-600 hover:bg-green-700 text-white">
                          Complete &amp; Pick Winner
                        </Button>
                      </>
                    )}
                    <button type="button" onClick={() => setExpandedId(expanded ? null : t.id)}>
                      {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </button>
                  </div>
                </div>
                {expanded && t.variants?.length > 0 && (
                  <div className="px-5 pb-5 space-y-4 bg-gray-50 border-t">
                    {t.variants.map((v) => {
                      const ve = variantEdits[v.id] ?? { subject_line: "", body_html: "", recipient_pct: "" };
                      return (
                        <div key={v.id} className="rounded-lg bg-white border p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-semibold text-gray-700 uppercase">Variant {v.label}</p>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>Sent: {v.sent}</span>
                              <span>Opens: {v.opens}</span>
                              <span>Clicks: {v.clicks}</span>
                              <span>Conv: {v.conversions}</span>
                            </div>
                          </div>
                          <div className="space-y-2">
                            <div className="space-y-1">
                              <label className="text-xs font-medium text-gray-700">Subject Line</label>
                              <input value={ve.subject_line}
                                onChange={(e) => setVariantEdits((f) => ({ ...f, [v.id]: { ...ve, subject_line: e.target.value } }))}
                                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium text-gray-700">Body HTML</label>
                              <textarea rows={3} value={ve.body_html}
                                onChange={(e) => setVariantEdits((f) => ({ ...f, [v.id]: { ...ve, body_html: e.target.value } }))}
                                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                            </div>
                            <div className="flex items-center gap-3">
                              <div className="space-y-1 w-32">
                                <label className="text-xs font-medium text-gray-700">Recipient %</label>
                                <input type="number" value={ve.recipient_pct}
                                  onChange={(e) => setVariantEdits((f) => ({ ...f, [v.id]: { ...ve, recipient_pct: e.target.value } }))}
                                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                              </div>
                              <Button size="sm" disabled={actionLoading === v.id + "_save"}
                                onClick={() => saveVariant(t.id, v.id)}
                                className="mt-4 bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
                                {actionLoading === v.id + "_save" ? "Saving…" : "Save Variant"}
                              </Button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Record stats modal */}
      {statsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-gray-900">Record Stats</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Variant</label>
                <select value={statsModal.variantId}
                  onChange={(e) => setStatsModal((m) => m ? { ...m, variantId: e.target.value } : null)}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                  {tests.find((t) => t.id === statsModal.testId)?.variants?.map((v) => (
                    <option key={v.id} value={v.id}>Variant {v.label}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { key: "sent" as const, label: "Sent" },
                  { key: "opens" as const, label: "Opens" },
                  { key: "clicks" as const, label: "Clicks" },
                  { key: "conversions" as const, label: "Conversions" },
                ].map(({ key, label }) => (
                  <div key={key} className="space-y-1">
                    <label className="text-xs font-medium text-gray-700">{label}</label>
                    <input type="number" value={statsModal[key]}
                      onChange={(e) => setStatsModal((m) => m ? { ...m, [key]: e.target.value } : null)}
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setStatsModal(null)}>Cancel</Button>
              <Button disabled={actionLoading === "stats_record"} onClick={recordStats}
                className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
                {actionLoading === "stats_record" ? "Recording…" : "Record"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
