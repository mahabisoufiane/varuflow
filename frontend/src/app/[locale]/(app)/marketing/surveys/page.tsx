"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Survey {
  id: string;
  name: string;
  question: string;
  status: "draft" | "active" | "closed";
  response_count: number;
  promoter_pct: number | null;
  passive_pct: number | null;
  detractor_pct: number | null;
}

interface SurveyResponse {
  id: string;
  score: number;
  comment: string | null;
  respondent_email: string | null;
  submitted_at: string;
}

interface TrendEntry {
  month: string;
  avg_score: number;
  response_count: number;
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  active: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
};

const DEFAULT_QUESTION = "On a scale of 0-10, how likely are you to recommend us to a friend or colleague?";

export default function SurveysPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [surveys, setSurveys] = useState<Survey[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [responses, setResponses] = useState<Record<string, SurveyResponse[]>>({});
  const [trend, setTrend] = useState<Record<string, TrendEntry[]>>({});
  const [showTrend, setShowTrend] = useState<Record<string, boolean>>({});

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ name: "", question: DEFAULT_QUESTION });

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
      const res = await fetch(apiUrl("/api/nps/surveys"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setSurveys(await res.json());
    } catch {
      toast.error("Failed to load surveys");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadResponses(id: string) {
    if (responses[id]) return;
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/nps/surveys/${id}/responses`), { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setResponses((r) => ({ ...r, [id]: data }));
      }
    } catch { /* silent */ }
  }

  async function loadTrend(id: string) {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/nps/surveys/${id}/trend`), { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setTrend((t) => ({ ...t, [id]: res.ok ? [] : [] }));
      if (res.ok) {
        const data = await res.json();
        setTrend((t) => ({ ...t, [id]: data }));
      }
    } catch { /* silent */ }
  }

  async function createSurvey() {
    if (!newForm.name.trim()) { toast.error("Name is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/nps/surveys"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: newForm.name, question: newForm.question }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Survey created");
      setShowNew(false);
      setNewForm({ name: "", question: DEFAULT_QUESTION });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function activateSurvey(id: string) {
    setActionLoading(id + "_activate");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/nps/surveys/${id}/activate`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed"); return; }
      toast.success("Survey activated");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function closeSurvey(id: string) {
    setActionLoading(id + "_close");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/nps/surveys/${id}/close`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed"); return; }
      toast.success("Survey closed");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  function handleExpand(id: string) {
    const isExpanding = expandedId !== id;
    setExpandedId(isExpanding ? id : null);
    if (isExpanding) loadResponses(id);
  }

  function npsScore(s: Survey) {
    if (s.promoter_pct == null || s.detractor_pct == null) return null;
    return Math.round(s.promoter_pct - s.detractor_pct);
  }

  // Score distribution from responses
  function scoreDistribution(id: string) {
    const resp = responses[id] ?? [];
    const dist: Record<number, number> = {};
    for (let i = 0; i <= 10; i++) dist[i] = 0;
    resp.forEach((r) => { if (r.score >= 0 && r.score <= 10) dist[r.score]++; });
    return dist;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">NPS Surveys</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Net Promoter Score surveys with trend tracking.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Survey
        </Button>
      </div>

      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Survey</h3>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Name *</label>
              <input value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Q2 2026 NPS"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Question</label>
              <textarea rows={2} value={newForm.question} onChange={(e) => setNewForm((f) => ({ ...f, question: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createSurvey}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Survey"}
            </Button>
          </div>
        </div>
      )}

      {loading && surveys.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {surveys.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-500">No surveys yet</div>
          ) : surveys.map((s) => {
            const expanded = expandedId === s.id;
            const score = npsScore(s);
            const dist = scoreDistribution(s.id);
            const maxCount = Math.max(...Object.values(dist), 1);
            const trendData = trend[s.id] ?? [];
            const isTrendVisible = showTrend[s.id];

            return (
              <div key={s.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => handleExpand(s.id)}>
                    <p className="text-sm font-medium text-gray-900">{s.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{s.question}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{s.response_count} responses</p>
                  </div>
                  {score != null && (
                    <div className="text-center">
                      <p className={`text-2xl font-bold ${score >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {score >= 0 ? "+" : ""}{score}
                      </p>
                      <p className="text-xs text-muted-foreground">NPS</p>
                    </div>
                  )}
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[s.status] ?? STATUS_COLOR.draft}`}>
                    {s.status}
                  </span>
                  <div className="flex items-center gap-2">
                    {s.status === "active" && (
                      <Button size="sm" variant="outline" disabled={actionLoading === s.id + "_close"}
                        onClick={() => closeSurvey(s.id)}>
                        Close
                      </Button>
                    )}
                    {s.status === "draft" && (
                      <Button size="sm" disabled={actionLoading === s.id + "_activate"}
                        onClick={() => activateSurvey(s.id)}
                        className="bg-green-600 hover:bg-green-700 text-white">
                        Activate
                      </Button>
                    )}
                    <button type="button" onClick={() => handleExpand(s.id)}>
                      {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </button>
                  </div>
                </div>

                {/* Promoter/Passive/Detractor bar */}
                {score != null && s.promoter_pct != null && s.passive_pct != null && s.detractor_pct != null && (
                  <div className="px-5 pb-2 flex items-center gap-1 h-3">
                    {[
                      { pct: s.promoter_pct, color: "bg-green-400" },
                      { pct: s.passive_pct, color: "bg-yellow-300" },
                      { pct: s.detractor_pct, color: "bg-red-400" },
                    ].map(({ pct, color }, i) => (
                      pct > 0 ? <div key={i} className={`h-3 rounded-sm ${color}`} style={{ width: `${pct}%` }} title={`${pct.toFixed(1)}%`} /> : null
                    ))}
                    <div className="flex-1" />
                    <span className="text-xs text-muted-foreground ml-2">
                      P:{s.promoter_pct.toFixed(0)}% Pa:{s.passive_pct.toFixed(0)}% D:{s.detractor_pct.toFixed(0)}%
                    </span>
                  </div>
                )}

                {expanded && (
                  <div className="px-5 pb-5 space-y-4 bg-gray-50 border-t">
                    {/* Score distribution histogram */}
                    {responses[s.id] && responses[s.id].length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-700 mb-2">Score Distribution</p>
                        <div className="flex items-end gap-1 h-16">
                          {Object.entries(dist).map(([score, count]) => (
                            <div key={score} className="flex flex-col items-center flex-1">
                              <div className="w-full rounded-t"
                                style={{ height: `${(count / maxCount) * 48}px`, backgroundColor: parseInt(score) >= 9 ? "#16a34a" : parseInt(score) >= 7 ? "#ca8a04" : "#dc2626", minHeight: count > 0 ? "4px" : "0" }}
                                title={`${count}`} />
                              <span className="text-xs text-gray-500 mt-1">{score}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Trend button */}
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline"
                        onClick={async () => {
                          if (!isTrendVisible) await loadTrend(s.id);
                          setShowTrend((t) => ({ ...t, [s.id]: !t[s.id] }));
                        }}>
                        {isTrendVisible ? "Hide Trend" : "Show Trend"}
                      </Button>
                    </div>

                    {isTrendVisible && trendData.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-semibold text-gray-700">Monthly Trend</p>
                        {trendData.map((entry) => (
                          <div key={entry.month} className="flex items-center gap-3 text-xs">
                            <span className="text-gray-500 w-20">{entry.month}</span>
                            <span className="font-medium text-gray-900">{entry.avg_score?.toFixed(1)}</span>
                            <span className="text-muted-foreground">({entry.response_count} responses)</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Responses table */}
                    <div>
                      <p className="text-xs font-semibold text-gray-700 mb-2">Responses</p>
                      {!responses[s.id] ? (
                        <div className="py-4 text-center"><RefreshCw className="h-4 w-4 animate-spin mx-auto text-muted-foreground" /></div>
                      ) : responses[s.id].length === 0 ? (
                        <p className="text-xs text-gray-500">No responses yet</p>
                      ) : (
                        <div className="rounded-lg border overflow-hidden">
                          <table className="w-full text-xs">
                            <thead className="bg-gray-100 border-b">
                              <tr>
                                <th className="px-3 py-2 text-left font-medium text-gray-700">Score</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700">Comment</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700">Email</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-700">Submitted</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 bg-white">
                              {responses[s.id].map((r) => (
                                <tr key={r.id}>
                                  <td className="px-3 py-2">
                                    <span className={`rounded-full px-2 py-0.5 font-semibold ${r.score >= 9 ? "bg-green-100 text-green-700" : r.score >= 7 ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-600"}`}>
                                      {r.score}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-gray-600 max-w-xs truncate">{r.comment ?? "—"}</td>
                                  <td className="px-3 py-2 text-gray-600">{r.respondent_email ?? "—"}</td>
                                  <td className="px-3 py-2 text-right text-gray-500">{new Date(r.submitted_at).toLocaleDateString()}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
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
