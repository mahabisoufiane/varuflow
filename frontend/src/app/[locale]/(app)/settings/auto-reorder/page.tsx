"use client";

/**
 * Settings → Auto-reorder (Item 16)
 *
 * Owner-facing UI for the auto-reorder workflow:
 *   1. Enable / disable the org switch
 *   2. Pick the weekly schedule (days + time)
 *   3. Notification email override
 *   4. Dry-run preview of what the next run would order
 *   5. Run history (last 10 rows)
 *   6. Manual "Run now" button
 *
 * Wires: GET/PUT /api/auto-reorder/settings, GET /preview, GET /runs,
 * POST /run. All endpoints fail gracefully — the surface refuses to lie
 * about state by falling back to the last known values when a fetch
 * errors (toast surfaces the detail).
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Repeat2, Loader2, Calendar, Clock, Mail, Eye, Play, History } from "lucide-react";

import { api } from "@/lib/api-client";

interface AutoReorderSettings {
  auto_reorder_enabled: boolean;
  auto_reorder_time: string; // "HH:MM"
  auto_reorder_days: string; // "MON,WED,FRI"
  auto_reorder_notify_email: string | null;
}

interface PreviewLine {
  product_id: string;
  product_name: string;
  sku: string;
  current_stock: number;
  reorder_level: number;
  suggested_qty: number;
  preferred_supplier_id: string | null;
  preferred_supplier_name: string | null;
  estimated_cost_sek: string;
}

interface RunRow {
  id: string;
  run_at: string;
  triggered_by: string;
  products_checked: number;
  purchase_orders_created: number;
  products_skipped: number;
  status: string;
  error_message: string | null;
}

interface RunResult {
  products_checked: number;
  purchase_orders_created: number;
  products_skipped: number;
  pos_created: Array<{
    po_id: string;
    supplier_name: string;
    items_count: number;
    total_sek: string;
  }>;
  errors: string[];
}

const DAYS: Array<{ code: string; label: string }> = [
  { code: "MON", label: "Mon" },
  { code: "TUE", label: "Tue" },
  { code: "WED", label: "Wed" },
  { code: "THU", label: "Thu" },
  { code: "FRI", label: "Fri" },
  { code: "SAT", label: "Sat" },
  { code: "SUN", label: "Sun" },
];

export default function AutoReorderSettingsPage() {
  const t = useTranslations("autoReorder");

  const [settings, setSettings] = useState<AutoReorderSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<PreviewLine[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [running, setRunning] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      const s = await api.get<AutoReorderSettings>("/api/auto-reorder/settings");
      setSettings(s);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }, []);

  const loadRuns = useCallback(async () => {
    try {
      const list = await api.get<RunRow[]>("/api/auto-reorder/runs");
      setRuns(list.slice(0, 10));
    } catch (e) {
      toast.error((e as Error).message);
    }
  }, []);

  useEffect(() => {
    loadSettings();
    loadRuns();
  }, [loadSettings, loadRuns]);

  async function save(next: Partial<AutoReorderSettings>) {
    if (!settings) return;
    setSaving(true);
    try {
      const saved = await api.put<AutoReorderSettings>("/api/auto-reorder/settings", {
        ...settings,
        ...next,
      });
      setSettings(saved);
      toast.success(t("run_success", { count: 0 }) || "Saved");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function toggleDay(code: string) {
    if (!settings) return;
    const current = new Set(
      settings.auto_reorder_days.split(",").map((d) => d.trim()).filter(Boolean),
    );
    if (current.has(code)) {
      current.delete(code);
    } else {
      current.add(code);
    }
    if (current.size === 0) {
      toast.error(t("run_failed"));
      return;
    }
    const ordered = DAYS.map((d) => d.code).filter((c) => current.has(c)).join(",");
    save({ auto_reorder_days: ordered });
  }

  async function onPreview() {
    setPreviewLoading(true);
    try {
      const lines = await api.get<PreviewLine[]>("/api/auto-reorder/preview");
      setPreview(lines);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function onRunNow() {
    setRunning(true);
    try {
      const result = await api.post<RunResult>("/api/auto-reorder/run", {});
      if (result.purchase_orders_created > 0) {
        toast.success(
          t("run_success", { count: result.purchase_orders_created }),
        );
      } else if (result.errors.length > 0) {
        toast.error(t("run_failed"));
      } else {
        toast.success(t("run_empty"));
      }
      await loadRuns();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const selectedDays = new Set(
    (settings?.auto_reorder_days ?? "").split(",").map((d) => d.trim()).filter(Boolean),
  );

  return (
    <div
      className="mx-auto max-w-4xl p-6 space-y-8"
      data-testid="auto-reorder-settings-page"
    >
      <header className="flex items-center gap-3">
        <Repeat2 className="h-6 w-6 text-indigo-400" />
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("description")}</p>
        </div>
      </header>

      {/* Enable */}
      <section
        data-testid="auto-reorder-enable-section"
        className="rounded-xl border border-white/10 p-5 space-y-3"
        style={{ background: "var(--vf-bg-surface)" }}
      >
        <label
          htmlFor="ar-enabled"
          className="flex items-center justify-between gap-4 cursor-pointer min-h-11"
        >
          <div className="flex-1">
            <div className="font-medium">{t("enabled_label")}</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {t("description")}
            </div>
          </div>
          <input
            id="ar-enabled"
            data-testid="auto-reorder-enable-toggle"
            type="checkbox"
            checked={!!settings?.auto_reorder_enabled}
            disabled={!settings || saving}
            onChange={(e) => save({ auto_reorder_enabled: e.target.checked })}
            className="h-5 w-5"
          />
        </label>
      </section>

      {/* Schedule */}
      <section
        data-testid="auto-reorder-schedule-section"
        className="rounded-xl border border-white/10 p-5 space-y-4"
        style={{ background: "var(--vf-bg-surface)" }}
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Calendar className="h-4 w-4" />
          <span>{t("schedule_label")}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {DAYS.map((d) => {
            const active = selectedDays.has(d.code);
            return (
              <button
                key={d.code}
                type="button"
                data-testid={`auto-reorder-day-${d.code}`}
                onClick={() => toggleDay(d.code)}
                disabled={!settings || saving}
                className={
                  "min-h-11 min-w-11 rounded-xl border px-3 text-sm font-medium transition " +
                  (active
                    ? "border-indigo-500/60 bg-indigo-500/20 text-indigo-200"
                    : "border-white/10 hover:bg-white/5")
                }
              >
                {d.label}
              </button>
            );
          })}
        </div>

        <label className="flex items-center gap-3 text-sm">
          <Clock className="h-4 w-4" />
          <span className="w-32">Time</span>
          <input
            data-testid="auto-reorder-time-input"
            type="time"
            value={settings?.auto_reorder_time ?? "06:00"}
            disabled={!settings || saving}
            onChange={(e) => save({ auto_reorder_time: e.target.value })}
            className="rounded-xl border border-white/10 bg-transparent px-3 py-2 min-h-11"
          />
        </label>
      </section>

      {/* Notification email */}
      <section
        data-testid="auto-reorder-email-section"
        className="rounded-xl border border-white/10 p-5 space-y-3"
        style={{ background: "var(--vf-bg-surface)" }}
      >
        <label className="flex items-center gap-2 text-sm font-semibold">
          <Mail className="h-4 w-4" />
          <span>{t("notify_email_label")}</span>
        </label>
        <input
          data-testid="auto-reorder-email-input"
          type="email"
          placeholder="owner@example.com"
          defaultValue={settings?.auto_reorder_notify_email ?? ""}
          disabled={!settings || saving}
          onBlur={(e) => save({ auto_reorder_notify_email: e.target.value || null })}
          className="w-full rounded-xl border border-white/10 bg-transparent px-3 py-2 min-h-11"
        />
        <p className="text-xs text-muted-foreground">{t("notify_email_hint")}</p>
      </section>

      {/* Preview */}
      <section
        data-testid="auto-reorder-preview-section"
        className="rounded-xl border border-white/10 p-5 space-y-4"
        style={{ background: "var(--vf-bg-surface)" }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Eye className="h-4 w-4" />
            <span>{t("preview_button")}</span>
          </div>
          <button
            type="button"
            data-testid="auto-reorder-preview-button"
            onClick={onPreview}
            disabled={previewLoading}
            className="min-h-11 rounded-xl bg-indigo-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {previewLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              t("preview_button")
            )}
          </button>
        </div>

        {preview !== null && preview.length === 0 && (
          <p
            data-testid="auto-reorder-preview-empty"
            className="text-sm text-muted-foreground"
          >
            {t("nothing_to_reorder")}
          </p>
        )}

        {preview !== null && preview.length > 0 && (
          <div
            data-testid="auto-reorder-preview-table"
            className="overflow-x-auto rounded-lg border border-white/10"
          >
            <table className="w-full text-sm">
              <thead className="bg-white/5">
                <tr>
                  <th className="px-3 py-2 text-left">{t("preview_product")}</th>
                  <th className="px-3 py-2 text-right">{t("preview_current_stock")}</th>
                  <th className="px-3 py-2 text-right">{t("preview_reorder_level")}</th>
                  <th className="px-3 py-2 text-right">{t("preview_suggested_qty")}</th>
                  <th className="px-3 py-2 text-left">{t("preview_supplier")}</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((l) => (
                  <tr key={l.product_id} className="border-t border-white/5">
                    <td className="px-3 py-2">
                      <div className="font-medium">{l.product_name}</div>
                      <div className="text-xs text-muted-foreground">{l.sku}</div>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {l.current_stock}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {l.reorder_level}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums font-semibold">
                      {l.suggested_qty}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {l.preferred_supplier_name ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Run now */}
      <section
        data-testid="auto-reorder-run-now-section"
        className="rounded-xl border border-white/10 p-5 flex items-center justify-between"
        style={{ background: "var(--vf-bg-surface)" }}
      >
        <div>
          <div className="font-semibold">{t("run_now_button")}</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {t("description")}
          </div>
        </div>
        <button
          type="button"
          data-testid="auto-reorder-run-now-button"
          onClick={onRunNow}
          disabled={running || !settings?.auto_reorder_enabled}
          className="min-h-14 rounded-xl bg-indigo-600 px-6 text-sm font-semibold text-white disabled:opacity-50 flex items-center gap-2"
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {t("run_now_button")}
        </button>
      </section>

      {/* Run history */}
      <section
        data-testid="auto-reorder-history-section"
        className="rounded-xl border border-white/10 p-5 space-y-3"
        style={{ background: "var(--vf-bg-surface)" }}
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <History className="h-4 w-4" />
          <span>{t("run_history_title")}</span>
        </div>
        <div
          data-testid="auto-reorder-history-table"
          className="overflow-x-auto rounded-lg border border-white/10"
        >
          <table className="w-full text-sm">
            <thead className="bg-white/5">
              <tr>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-left">{t("run_triggered_by")}</th>
                <th className="px-3 py-2 text-right">{t("run_pos_created")}</th>
                <th className="px-3 py-2 text-left">{t("run_status")}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-white/5">
                  <td className="px-3 py-2">
                    {new Date(r.run_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {r.triggered_by}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {r.purchase_orders_created}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold " +
                        (r.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-300"
                          : r.status === "partial"
                          ? "bg-amber-500/10 text-amber-300"
                          : "bg-red-500/10 text-red-300")
                      }
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-3 py-4 text-center text-muted-foreground"
                  >
                    —
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
