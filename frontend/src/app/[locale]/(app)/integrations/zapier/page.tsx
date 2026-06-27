"use client";

import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import {
  Zap, Plus, Trash2, Play, CheckCircle2, XCircle, Clock, AlertTriangle, Copy,
} from "lucide-react";

type HookType = "zapier" | "make" | "generic";

const EVENT_TYPES = [
  "invoice.created", "invoice.paid", "invoice.overdue",
  "customer.created", "customer.updated",
  "product.low_stock", "order.created", "order.shipped",
];

interface ZapierHook {
  id: string;
  name: string;
  subscribe_url: string;
  event_type: string;
  hook_type: HookType;
  is_active: boolean;
  created_at: string;
  last_triggered_at: string | null;
}

interface EventLog {
  id: string;
  hook_id: string;
  event_type: string;
  status: "success" | "failed" | "pending";
  triggered_at: string;
  response_code: number | null;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  success: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  failed:  <XCircle     className="h-3.5 w-3.5 text-red-400"     />,
  pending: <Clock       className="h-3.5 w-3.5 text-amber-400"   />,
};

const STATUS_CLASS: Record<string, string> = {
  success: "pill-paid",
  failed:  "pill-overdue",
  pending: "inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400",
};

export default function ZapierPage() {
  const t      = useTranslations();
  const router = useRouter();
  const locale = useLocale();

  const [hooks, setHooks]         = useState<ZapierHook[]>([]);
  const [logs, setLogs]           = useState<EventLog[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [firing, setFiring]       = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "",
    subscribe_url: "",
    event_type: EVENT_TYPES[0],
    hook_type: "zapier" as HookType,
  });

  useEffect(() => {
    Promise.all([
      api.get<ZapierHook[]>("/api/zapier/hooks"),
      api.get<EventLog[]>("/api/zapier/logs"),
    ])
      .then(([h, l]) => { setHooks(h); setLogs(l); })
      .catch((e: Error) => {
        if (e.message.includes("session")) router.push(`/${locale}/auth/login`);
        else toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await api.post<ZapierHook>("/api/zapier/hooks", form);
      setHooks(prev => [created, ...prev]);
      setShowForm(false);
      setForm({ name: "", subscribe_url: "", event_type: EVENT_TYPES[0], hook_type: "zapier" });
      toast.success(t("hookCreated"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/api/zapier/hooks/${id}`);
      setHooks(prev => prev.filter(h => h.id !== id));
      toast.success(t("hookDeleted"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleTest(id: string) {
    setFiring(id);
    try {
      await api.post(`/api/zapier/hooks/${id}/test`, {});
      toast.success(t("hookTestFired"));
      const updated = await api.get<EventLog[]>("/api/zapier/logs");
      setLogs(updated);
    } catch (err: unknown) { toast.error((err as Error).message); }
    finally { setFiring(null); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("zapierConnector")}</h1>
          <p className="text-xs vf-text-m mt-0.5">{t("zapierDesc")}</p>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />{t("addHook")}
        </button>
      </div>

      {showForm && (
        <div className="vf-section p-5">
          <h2 className="text-[13px] font-semibold vf-text-1 mb-4">{t("newHook")}</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium vf-text-m block mb-1">{t("hookName")}</label>
              <input required value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="My Zapier hook" className="vf-input text-xs w-full" />
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-1">{t("subscribeUrl")}</label>
              <input required type="url" value={form.subscribe_url}
                onChange={e => setForm(f => ({ ...f, subscribe_url: e.target.value }))}
                placeholder="https://hooks.zapier.com/..." className="vf-input text-xs w-full" />
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-1">{t("eventType")}</label>
              <select value={form.event_type}
                onChange={e => setForm(f => ({ ...f, event_type: e.target.value }))}
                className="vf-input text-xs w-full">
                {EVENT_TYPES.map(ev => <option key={ev} value={ev}>{ev}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-1">{t("hookType")}</label>
              <select value={form.hook_type}
                onChange={e => setForm(f => ({ ...f, hook_type: e.target.value as HookType }))}
                className="vf-input text-xs w-full">
                <option value="zapier">Zapier</option>
                <option value="make">Make (Integromat)</option>
                <option value="generic">Generic</option>
              </select>
            </div>
            <div className="sm:col-span-2 flex gap-2 justify-end">
              <button type="button" onClick={() => setShowForm(false)}
                className="rounded-lg px-4 py-2 text-xs font-medium vf-text-m"
                style={{ border: "1px solid var(--vf-border)" }}>
                {t("cancel")}
              </button>
              <button type="submit" className="vf-btn text-xs">{t("create")}</button>
            </div>
          </form>
        </div>
      )}

      {/* Hooks list */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("activeHooks")}</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2].map(i => <div key={i} className="h-14 skeleton rounded-xl" />)}
          </div>
        ) : hooks.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              style={{ background: "var(--vf-bg-elevated)" }}>
              <Zap className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{t("noHooks")}</p>
            <p className="text-xs vf-text-m mt-1">{t("addHookToGet Started")}</p>
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--vf-divider)" }}>
            {hooks.map(hook => (
              <div key={hook.id} className="flex items-center gap-4 px-5 py-4 vf-row">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                  style={{ background: "var(--vf-bg-elevated)" }}>
                  <Zap className="h-4 w-4 vf-text-m" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1">{hook.name}</p>
                  <p className="text-xs vf-text-m truncate">{hook.event_type} · {hook.hook_type}</p>
                  {hook.last_triggered_at && (
                    <p className="text-[11px] vf-text-m mt-0.5 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(hook.last_triggered_at).toLocaleString()}
                    </p>
                  )}
                </div>
                <button onClick={() => {
                  navigator.clipboard.writeText(hook.subscribe_url);
                  toast.success(t("copied"));
                }} className="flex h-8 w-8 items-center justify-center rounded-lg vf-text-m hover:vf-text-1 transition-colors">
                  <Copy className="h-4 w-4" />
                </button>
                <button onClick={() => handleTest(hook.id)} disabled={firing === hook.id}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-500/10 transition-colors">
                  <Play className={`h-3.5 w-3.5 ${firing === hook.id ? "animate-pulse" : ""}`} />
                  {t("test")}
                </button>
                <button onClick={() => handleDelete(hook.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-red-400 hover:bg-red-500/10 transition-colors">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Event log */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("eventLog")}</h2>
        </div>
        {logs.length === 0 ? (
          <div className="py-10 text-center">
            <AlertTriangle className="mx-auto h-6 w-6 vf-text-m mb-2" />
            <p className="text-xs vf-text-m">{t("noEventLogs")}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--vf-border)", background: "var(--vf-bg-elevated)" }}>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("event")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden sm:table-cell">{t("time")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("status")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden md:table-cell">{t("responseCode")}</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(0, 50).map(log => (
                <tr key={log.id} className="vf-row" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
                  <td className="px-5 py-3 font-mono text-xs vf-text-1">{log.event_type}</td>
                  <td className="px-5 py-3 text-xs vf-text-m hidden sm:table-cell">
                    {new Date(log.triggered_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <span className={STATUS_CLASS[log.status]}>
                      {STATUS_ICON[log.status]}{log.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs vf-text-m hidden md:table-cell">
                    {log.response_code ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
