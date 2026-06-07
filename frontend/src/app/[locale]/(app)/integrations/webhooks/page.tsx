"use client";

import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import styles from "./page.module.scss";
import {
  Webhook, Plus, Trash2, Eye, RotateCcw, CheckCircle2, XCircle, Clock,
} from "lucide-react";

interface CustomerWebhook {
  id: string;
  customer_id: string;
  customer_name: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

interface DeliveryLog {
  id: string;
  event: string;
  status: "success" | "failed" | "pending";
  delivered_at: string;
  response_code: number | null;
  response_body: string | null;
}

const ALL_EVENTS = [
  "invoice.created", "invoice.paid", "invoice.overdue", "invoice.cancelled",
  "payment.received", "order.shipped", "order.delivered",
];

export default function WebhooksPage() {
  const t      = useTranslations();
  const router = useRouter();
  const locale = useLocale();

  const [webhooks, setWebhooks]     = useState<CustomerWebhook[]>([]);
  const [loading, setLoading]       = useState(true);
  const [showDrawer, setShowDrawer] = useState(false);
  const [historyFor, setHistoryFor] = useState<string | null>(null);
  const [history, setHistory]       = useState<DeliveryLog[]>([]);
  const [rotating, setRotating]     = useState<string | null>(null);

  const [form, setForm] = useState({
    customer_id: "",
    url: "",
    events: [] as string[],
  });

  useEffect(() => {
    api.get<CustomerWebhook[]>("/api/webhooks")
      .then(setWebhooks)
      .catch((e: Error) => {
        if (e.message.includes("session")) router.push(`/${locale}/auth/login`);
        else toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await api.post<CustomerWebhook>("/api/webhooks", form);
      setWebhooks(prev => [created, ...prev]);
      setShowDrawer(false);
      setForm({ customer_id: "", url: "", events: [] });
      toast.success(t("webhookCreated"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/api/webhooks/${id}`);
      setWebhooks(prev => prev.filter(w => w.id !== id));
      toast.success(t("webhookDeleted"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleRotateSecret(id: string) {
    setRotating(id);
    try {
      await api.post(`/api/webhooks/${id}/rotate-secret`, {});
      toast.success(t("secretRotated"));
    } catch (err: unknown) { toast.error((err as Error).message); }
    finally { setRotating(null); }
  }

  async function handleViewHistory(id: string) {
    setHistoryFor(id);
    try {
      const logs = await api.get<DeliveryLog[]>(`/api/webhooks/${id}/deliveries`);
      setHistory(logs);
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  function toggleEvent(ev: string) {
    setForm(f => ({
      ...f,
      events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev],
    }));
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("webhooks")}</h1>
          <p className="text-xs vf-text-m mt-0.5">{t("webhooksDesc")}</p>
        </div>
        <button onClick={() => setShowDrawer(v => !v)} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />{t("addWebhook")}
        </button>
      </div>

      {/* Create webhook drawer */}
      {showDrawer && (
        <div className="vf-section p-5">
          <h2 className="text-[13px] font-semibold vf-text-1 mb-4">{t("newWebhook")}</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("customerId")}</label>
                <input required value={form.customer_id}
                  onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}
                  placeholder="cust_123" className="vf-input text-xs w-full" />
              </div>
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("endpointUrl")}</label>
                <input required type="url" value={form.url}
                  onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                  placeholder="https://example.com/webhook" className="vf-input text-xs w-full" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-2">{t("events")}</label>
              <div className="flex flex-wrap gap-2">
                {ALL_EVENTS.map(ev => (
                  <button type="button" key={ev}
                    onClick={() => toggleEvent(ev)}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                      form.events.includes(ev)
                        ? "bg-indigo-500 text-white"
                        : "vf-text-m hover:vf-text-1"
                    }`}
                    style={!form.events.includes(ev) ? { border: "1px solid var(--vf-border)" } : {}}>
                    {ev}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowDrawer(false)}
                className="rounded-lg px-4 py-2 text-xs font-medium vf-text-m vf-btn-secondary">
                {t("cancel")}
              </button>
              <button type="submit" className="vf-btn text-xs">{t("create")}</button>
            </div>
          </form>
        </div>
      )}

      {/* Webhooks table */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("customerWebhooks")}</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2, 3].map(i => <div key={i} className="h-12 skeleton rounded-xl" />)}
          </div>
        ) : webhooks.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              >
              <Webhook className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{t("noWebhooks")}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className={styles.tableHead}>
              <tr>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("customer")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden md:table-cell">{t("url")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden sm:table-cell">{t("events")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("status")}</th>
                <th className="px-5 py-3 text-right text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map(wh => (
                <tr key={wh.id} className={"vf-row " + styles.tableRow}>
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-semibold vf-text-1">{wh.customer_name}</p>
                    <p className="text-xs vf-text-m font-mono">{wh.customer_id}</p>
                  </td>
                  <td className="px-5 py-3.5 hidden md:table-cell">
                    <p className="text-xs vf-text-m truncate max-w-xs">{wh.url}</p>
                  </td>
                  <td className="px-5 py-3.5 hidden sm:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {wh.events.slice(0, 3).map(ev => (
                        <span key={ev} className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400">
                          {ev}
                        </span>
                      ))}
                      {wh.events.length > 3 && (
                        <span className="text-[11px] vf-text-m">+{wh.events.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    {wh.is_active ? (
                      <span className="pill-paid"><CheckCircle2 className="h-3 w-3" />{t("active")}</span>
                    ) : (
                      <span className="pill-overdue"><XCircle className="h-3 w-3" />{t("inactive")}</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleViewHistory(wh.id)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg vf-text-m hover:vf-text-1 hover:bg-indigo-500/10 transition-colors"
                        title={t("deliveryHistory")}>
                        <Eye className="h-4 w-4" />
                      </button>
                      <button onClick={() => handleRotateSecret(wh.id)} disabled={rotating === wh.id}
                        className="flex h-8 w-8 items-center justify-center rounded-lg vf-text-m hover:vf-text-1 hover:bg-amber-500/10 transition-colors"
                        title={t("rotateSecret")}>
                        <RotateCcw className={`h-4 w-4 ${rotating === wh.id ? "animate-spin" : ""}`} />
                      </button>
                      <button onClick={() => handleDelete(wh.id)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-red-400 hover:bg-red-500/10 transition-colors">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Delivery history modal */}
      {historyFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setHistoryFor(null)} />
          <div className="relative w-full max-w-2xl vf-section rounded-2xl overflow-hidden">
            <div className="vf-section-header">
              <h2 className="text-[13px] font-semibold vf-text-1">{t("deliveryHistory")}</h2>
              <button onClick={() => setHistoryFor(null)}
                className="text-xs vf-text-m hover:vf-text-1 transition-colors px-3 py-1 rounded-lg vf-btn-secondary">
                {t("close")}
              </button>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {history.length === 0 ? (
                <p className="py-10 text-center text-xs vf-text-m">{t("noDeliveryHistory")}</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr >
                      <th className="px-5 py-2 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("event")}</th>
                      <th className="px-5 py-2 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("time")}</th>
                      <th className="px-5 py-2 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("status")}</th>
                      <th className="px-5 py-2 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("code")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(log => (
                      <tr key={log.id} className={styles.dividerTop}>
                        <td className="px-5 py-2.5 font-mono text-xs vf-text-1">{log.event}</td>
                        <td className="px-5 py-2.5 text-xs vf-text-m">{new Date(log.delivered_at).toLocaleString()}</td>
                        <td className="px-5 py-2.5">
                          <span className={STATUS_CLASS[log.status]}>
                            {STATUS_ICON[log.status]}{log.status}
                          </span>
                        </td>
                        <td className="px-5 py-2.5 text-xs vf-text-m">{log.response_code ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
