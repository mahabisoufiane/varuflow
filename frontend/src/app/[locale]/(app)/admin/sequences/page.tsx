"use client";

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";

// ── Types ──────────────────────────────────────────────────────────────────────

type TrialSequenceRow = {
  id: string;
  name: string;
  locale: string;
  enabled: boolean;
  steps_count: number;
  active_enrollments: number;
  completion_rate: number;
};

type TrialEnrollmentRow = {
  id: string;
  org_id: string;
  user_email: string;
  current_step: number;
  next_send_at: string | null;
  locale: string;
  exit_reason: string | null;
  completed_at: string | null;
};

type StepStatRow = {
  step_number: number;
  template_key: string;
  sent: number;
  opened: number;
  clicked: number;
};

type SummaryResponse = {
  sequences: TrialSequenceRow[];
  total_active_enrollments: number;
  emails_sent_this_week: number;
  conversion_rate: number;
  avg_completion_rate: number;
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function LocaleBadge({ locale }: { locale: string }) {
  const colorMap: Record<string, string> = {
    en: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    sv: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    ar: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    fr: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    no: "bg-red-500/20 text-red-400 border-red-500/30",
    da: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  };
  const style =
    colorMap[locale.toLowerCase()] ??
    "bg-slate-500/20 text-slate-400 border-slate-500/30";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border uppercase ${style}`}
    >
      {locale}
    </span>
  );
}

function ExitReasonBadge({ reason }: { reason: string | null }) {
  if (!reason) return <span className="text-slate-600 text-xs">—</span>;
  const styles: Record<string, string> = {
    completed: "bg-green-500/20 text-green-400 border-green-500/30",
    converted: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    manual: "bg-slate-500/20 text-slate-400 border-slate-500/30",
    churned: "bg-red-500/20 text-red-400 border-red-500/30",
  };
  const style =
    styles[reason] ?? "bg-slate-500/20 text-slate-400 border-slate-500/30";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border capitalize ${style}`}
    >
      {reason}
    </span>
  );
}

function CompletionBar({ pct }: { pct: number }) {
  const color =
    pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-300">{pct}%</span>
    </div>
  );
}

function SummaryTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
      <p className={`text-xs mb-1 ${accent ?? "text-slate-400"}`}>{label}</p>
      <p className={`text-2xl font-bold ${accent ?? "text-slate-100"}`}>
        {value}
      </p>
    </div>
  );
}

function pct(num: number, denom: number): string {
  if (denom === 0) return "0%";
  return `${Math.round((num / denom) * 100)}%`;
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AdminSequencesPage() {
  const [adminKey, setAdminKey] = useState<string>(() =>
    typeof window !== "undefined"
      ? sessionStorage.getItem("admin_api_key") ?? ""
      : ""
  );
  const [keyInput, setKeyInput] = useState("");

  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const [selectedSequenceId, setSelectedSequenceId] = useState<string | null>(
    null
  );
  const [enrollments, setEnrollments] = useState<TrialEnrollmentRow[]>([]);
  const [stepStats, setStepStats] = useState<StepStatRow[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [forcingExit, setForcingExit] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

  const headers = useCallback(
    () => ({
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
    }),
    [adminKey]
  );

  const fetchSummary = useCallback(
    async (key: string) => {
      setLoading(true);
      try {
        const res = await fetch(`${apiBase}/api/admin/trial/sequences`, {
          headers: { "X-Admin-Key": key },
        });
        if (res.status === 401 || res.status === 403) {
          toast.error("Invalid admin key.");
          setAdminKey("");
          sessionStorage.removeItem("admin_api_key");
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: SummaryResponse = await res.json();
        setSummary(data);
      } catch {
        toast.error("Failed to load sequences.");
      } finally {
        setLoading(false);
      }
    },
    [apiBase]
  );

  useEffect(() => {
    if (adminKey) {
      fetchSummary(adminKey);
    }
  }, [adminKey, fetchSummary]);

  const fetchDetail = useCallback(
    async (seqId: string) => {
      setLoadingDetail(true);
      try {
        const [enrollRes, statsRes] = await Promise.all([
          fetch(`${apiBase}/api/admin/trial/sequences/${seqId}/enrollments`, {
            headers: headers(),
          }),
          fetch(`${apiBase}/api/admin/trial/sequences/${seqId}/stats`, {
            headers: headers(),
          }),
        ]);
        if (!enrollRes.ok || !statsRes.ok) throw new Error("Detail fetch failed");
        const [enrollData, statsData] = await Promise.all([
          enrollRes.json() as Promise<TrialEnrollmentRow[]>,
          statsRes.json() as Promise<StepStatRow[]>,
        ]);
        setEnrollments(enrollData);
        setStepStats(statsData);
      } catch {
        toast.error("Failed to load sequence detail.");
      } finally {
        setLoadingDetail(false);
      }
    },
    [apiBase, headers]
  );

  function handleSelectSequence(id: string) {
    if (selectedSequenceId === id) {
      setSelectedSequenceId(null);
      setEnrollments([]);
      setStepStats([]);
    } else {
      setSelectedSequenceId(id);
      fetchDetail(id);
    }
  }

  async function handleForceExit(enrollmentId: string) {
    setForcingExit(enrollmentId);
    try {
      const res = await fetch(
        `${apiBase}/api/admin/trial/enrollments/${enrollmentId}/exit`,
        {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ reason: "manual" }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success("Enrollment exited.");
      setEnrollments((prev) =>
        prev.map((e) =>
          e.id === enrollmentId ? { ...e, exit_reason: "manual" } : e
        )
      );
    } catch {
      toast.error("Failed to exit enrollment.");
    } finally {
      setForcingExit(null);
    }
  }

  function handleKeySubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!keyInput.trim()) return;
    sessionStorage.setItem("admin_api_key", keyInput.trim());
    setAdminKey(keyInput.trim());
  }

  // ── PIN gate ─────────────────────────────────────────────────────────────────

  if (!adminKey) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 w-full max-w-sm">
          <h1 className="text-lg font-semibold text-slate-100 mb-1">
            Admin Sequences Dashboard
          </h1>
          <p className="text-sm text-slate-400 mb-6">
            Enter your admin key to continue.
          </p>
          <form onSubmit={handleKeySubmit} className="space-y-4">
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="Admin key"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
            <button
              type="submit"
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              Enter admin key
            </button>
          </form>
        </div>
      </div>
    );
  }

  const sequences = summary?.sequences ?? [];
  const selectedSeq = sequences.find((s) => s.id === selectedSequenceId) ?? null;

  // ── Dashboard ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0f172a] p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-100">
              Trial Onboarding Sequences
            </h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Manage 14-day trial email sequences
            </p>
          </div>
          <button
            onClick={() => fetchSummary(adminKey)}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {/* Summary tiles */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <SummaryTile
              label="Active enrollments"
              value={summary.total_active_enrollments}
            />
            <SummaryTile
              label="Emails sent this week"
              value={summary.emails_sent_this_week}
              accent="text-indigo-400"
            />
            <SummaryTile
              label="Trial → paid conversion"
              value={`${summary.conversion_rate}%`}
              accent="text-green-400"
            />
            <SummaryTile
              label="Avg completion rate"
              value={`${summary.avg_completion_rate}%`}
              accent="text-yellow-400"
            />
          </div>
        )}

        {/* Sequences table */}
        {loading ? (
          <div className="text-center py-16 text-slate-500 text-sm">
            Loading sequences…
          </div>
        ) : sequences.length === 0 ? (
          <div className="text-center py-16 text-slate-500 text-sm">
            No sequences found.
          </div>
        ) : (
          <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden mb-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Sequence
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Locale
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Enabled
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Steps
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Active
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Completion
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {sequences.map((seq) => (
                  <tr
                    key={seq.id}
                    className={`hover:bg-slate-800/50 cursor-pointer transition-colors ${
                      selectedSequenceId === seq.id ? "bg-slate-800/40" : ""
                    }`}
                    onClick={() => handleSelectSequence(seq.id)}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-200">{seq.name}</p>
                      <p className="text-xs text-slate-500 font-mono">{seq.id}</p>
                    </td>
                    <td className="px-4 py-3">
                      <LocaleBadge locale={seq.locale} />
                    </td>
                    <td className="px-4 py-3">
                      <EnabledToggle
                        seqId={seq.id}
                        enabled={seq.enabled}
                        adminKey={adminKey}
                        apiBase={apiBase}
                        onToggle={(enabled) => {
                          setSummary((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  sequences: prev.sequences.map((s) =>
                                    s.id === seq.id ? { ...s, enabled } : s
                                  ),
                                }
                              : prev
                          );
                        }}
                      />
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                      {seq.steps_count}
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                      {seq.active_enrollments}
                    </td>
                    <td className="px-4 py-3">
                      <CompletionBar pct={seq.completion_rate} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectSequence(seq.id);
                        }}
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-600/40 transition-colors"
                      >
                        {selectedSequenceId === seq.id ? "Close" : "View"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Detail panels */}
        {selectedSeq && (
          <div className="space-y-6">
            {/* Enrollments panel */}
            <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-700">
                <h2 className="text-sm font-semibold text-slate-200">
                  Active Enrollments — {selectedSeq.name}
                </h2>
              </div>
              {loadingDetail ? (
                <div className="text-center py-10 text-slate-500 text-sm">
                  Loading enrollments…
                </div>
              ) : enrollments.length === 0 ? (
                <div className="text-center py-10 text-slate-500 text-sm">
                  No enrollments found.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Email
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Step
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Next send
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Locale
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Exit reason
                      </th>
                      <th className="text-right px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {enrollments.map((enr) => (
                      <tr
                        key={enr.id}
                        className="hover:bg-slate-800/30 transition-colors"
                      >
                        <td className="px-4 py-2.5">
                          <p className="text-slate-200 text-xs">{enr.user_email}</p>
                          <p className="text-xs text-slate-500 font-mono">
                            {enr.org_id}
                          </p>
                        </td>
                        <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">
                          {enr.current_step}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400 text-xs">
                          {enr.next_send_at
                            ? new Date(enr.next_send_at).toLocaleString()
                            : "—"}
                        </td>
                        <td className="px-4 py-2.5">
                          <LocaleBadge locale={enr.locale} />
                        </td>
                        <td className="px-4 py-2.5">
                          <ExitReasonBadge reason={enr.exit_reason} />
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {!enr.exit_reason && (
                            <button
                              onClick={() => handleForceExit(enr.id)}
                              disabled={forcingExit === enr.id}
                              className="px-2.5 py-1 text-xs font-semibold rounded bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/40 transition-colors disabled:opacity-50"
                            >
                              {forcingExit === enr.id
                                ? "Exiting…"
                                : "Force exit"}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Email performance panel */}
            <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-700">
                <h2 className="text-sm font-semibold text-slate-200">
                  Email Performance — {selectedSeq.name}
                </h2>
              </div>
              {loadingDetail ? (
                <div className="text-center py-10 text-slate-500 text-sm">
                  Loading stats…
                </div>
              ) : stepStats.length === 0 ? (
                <div className="text-center py-10 text-slate-500 text-sm">
                  No step stats found.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Step
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Template
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Sent
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Open rate
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Click rate
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {stepStats.map((stat) => (
                      <tr
                        key={stat.step_number}
                        className="hover:bg-slate-800/30 transition-colors"
                      >
                        <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">
                          #{stat.step_number}
                        </td>
                        <td className="px-4 py-2.5 text-slate-200 text-xs font-mono">
                          {stat.template_key}
                        </td>
                        <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">
                          {stat.sent}
                        </td>
                        <td className="px-4 py-2.5">
                          <span
                            className={`text-xs font-mono ${
                              stat.sent > 0 && stat.opened / stat.sent >= 0.3
                                ? "text-green-400"
                                : "text-slate-400"
                            }`}
                          >
                            {pct(stat.opened, stat.sent)}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span
                            className={`text-xs font-mono ${
                              stat.sent > 0 && stat.clicked / stat.sent >= 0.1
                                ? "text-blue-400"
                                : "text-slate-400"
                            }`}
                          >
                            {pct(stat.clicked, stat.sent)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Enabled toggle (isolated to avoid re-rendering the whole table) ─────────────

function EnabledToggle({
  seqId,
  enabled,
  adminKey,
  apiBase,
  onToggle,
}: {
  seqId: string;
  enabled: boolean;
  adminKey: string;
  apiBase: string;
  onToggle: (enabled: boolean) => void;
}) {
  const [pending, setPending] = useState(false);

  async function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    setPending(true);
    try {
      const res = await fetch(
        `${apiBase}/api/admin/trial/sequences/${seqId}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Key": adminKey,
          },
          body: JSON.stringify({ enabled: !enabled }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onToggle(!enabled);
      toast.success(`Sequence ${!enabled ? "enabled" : "disabled"}.`);
    } catch {
      toast.error("Failed to update sequence.");
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={pending}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${
        enabled ? "bg-indigo-600" : "bg-slate-700"
      }`}
      aria-label={enabled ? "Disable sequence" : "Enable sequence"}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
          enabled ? "translate-x-4" : "translate-x-1"
        }`}
      />
    </button>
  );
}
