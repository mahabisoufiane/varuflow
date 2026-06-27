"use client";

import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { Bell, Plus, Pencil, Trash2, CheckCircle2, XCircle, Clock } from "lucide-react";

type DeliveryChannel = "email" | "sms" | "in_app" | "webhook";
type Schedule = "realtime" | "hourly" | "daily" | "weekly";

const ALL_EVENT_TYPES = [
  "invoice.created", "invoice.paid", "invoice.overdue", "invoice.cancelled",
  "customer.created", "customer.updated",
  "product.low_stock", "payment.received", "order.shipped",
];

const CHANNEL_OPTIONS: { value: DeliveryChannel; label: string }[] = [
  { value: "email",    label: "Email"    },
  { value: "sms",      label: "SMS"      },
  { value: "in_app",   label: "In-App"   },
  { value: "webhook",  label: "Webhook"  },
];

const SCHEDULE_OPTIONS: { value: Schedule; label: string }[] = [
  { value: "realtime", label: "Real-time" },
  { value: "hourly",   label: "Hourly digest" },
  { value: "daily",    label: "Daily digest"  },
  { value: "weekly",   label: "Weekly digest" },
];

interface NotificationBundle {
  id: string;
  bundle_name: string;
  event_types: string[];
  delivery_channel: DeliveryChannel;
  schedule: Schedule;
  digest_time: string | null;
  is_active: boolean;
  created_at: string;
}

const emptyForm = (): Omit<NotificationBundle, "id" | "created_at"> => ({
  bundle_name: "",
  event_types: [],
  delivery_channel: "email",
  schedule: "realtime",
  digest_time: null,
  is_active: true,
});

export default function NotificationBundlesPage() {
  const t      = useTranslations();
  const router = useRouter();
  const locale = useLocale();

  const [bundles, setBundles]     = useState<NotificationBundle[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [editing, setEditing]     = useState<string | null>(null);
  const [form, setForm]           = useState(emptyForm());

  useEffect(() => {
    api.get<NotificationBundle[]>("/api/notification-bundles")
      .then(setBundles)
      .catch((e: Error) => {
        if (e.message.includes("session")) router.push(`/${locale}/auth/login`);
        else toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  function startEdit(bundle: NotificationBundle) {
    setEditing(bundle.id);
    setForm({
      bundle_name:      bundle.bundle_name,
      event_types:      bundle.event_types,
      delivery_channel: bundle.delivery_channel,
      schedule:         bundle.schedule,
      digest_time:      bundle.digest_time,
      is_active:        bundle.is_active,
    });
    setShowForm(true);
  }

  function cancelForm() {
    setShowForm(false);
    setEditing(null);
    setForm(emptyForm());
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editing) {
        const updated = await api.put<NotificationBundle>(`/api/notification-bundles/${editing}`, form);
        setBundles(prev => prev.map(b => b.id === editing ? updated : b));
        toast.success(t("bundleUpdated"));
      } else {
        const created = await api.post<NotificationBundle>("/api/notification-bundles", form);
        setBundles(prev => [created, ...prev]);
        toast.success(t("bundleCreated"));
      }
      cancelForm();
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/api/notification-bundles/${id}`);
      setBundles(prev => prev.filter(b => b.id !== id));
      toast.success(t("bundleDeleted"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleToggle(bundle: NotificationBundle) {
    try {
      const updated = await api.patch<NotificationBundle>(
        `/api/notification-bundles/${bundle.id}`,
        { is_active: !bundle.is_active }
      );
      setBundles(prev => prev.map(b => b.id === bundle.id ? updated : b));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  function toggleEventType(ev: string) {
    setForm(f => ({
      ...f,
      event_types: f.event_types.includes(ev)
        ? f.event_types.filter(e => e !== ev)
        : [...f.event_types, ev],
    }));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("notificationBundles")}</h1>
          <p className="text-xs vf-text-m mt-0.5">{t("notificationBundlesDesc")}</p>
        </div>
        <button onClick={() => { setEditing(null); setForm(emptyForm()); setShowForm(v => !v); }}
          className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />{t("createBundle")}
        </button>
      </div>

      {showForm && (
        <div className="vf-section p-5">
          <h2 className="text-[13px] font-semibold vf-text-1 mb-4">
            {editing ? t("editBundle") : t("newBundle")}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("bundleName")}</label>
                <input required value={form.bundle_name}
                  onChange={e => setForm(f => ({ ...f, bundle_name: e.target.value }))}
                  placeholder="Daily invoice digest" className="vf-input text-xs w-full" />
              </div>
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("deliveryChannel")}</label>
                <select value={form.delivery_channel}
                  onChange={e => setForm(f => ({ ...f, delivery_channel: e.target.value as DeliveryChannel }))}
                  className="vf-input text-xs w-full">
                  {CHANNEL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("schedule")}</label>
                <select value={form.schedule}
                  onChange={e => setForm(f => ({ ...f, schedule: e.target.value as Schedule }))}
                  className="vf-input text-xs w-full">
                  {SCHEDULE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              {(form.schedule === "daily" || form.schedule === "weekly") && (
                <div>
                  <label className="text-xs font-medium vf-text-m block mb-1">{t("digestTime")}</label>
                  <input type="time" value={form.digest_time ?? ""}
                    onChange={e => setForm(f => ({ ...f, digest_time: e.target.value || null }))}
                    className="vf-input text-xs w-full" />
                </div>
              )}
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-2">{t("eventTypes")}</label>
              <div className="flex flex-wrap gap-2">
                {ALL_EVENT_TYPES.map(ev => (
                  <button type="button" key={ev}
                    onClick={() => toggleEventType(ev)}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                      form.event_types.includes(ev)
                        ? "bg-indigo-500 text-white"
                        : "vf-text-m hover:vf-text-1"
                    }`}
                    style={!form.event_types.includes(ev) ? { border: "1px solid var(--vf-border)" } : {}}>
                    {ev}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={cancelForm}
                className="vf-btn-secondary text-xs">
                {t("cancel")}
              </button>
              <button type="submit" className="vf-btn text-xs">
                {editing ? t("save") : t("create")}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("bundles")}</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2, 3].map(i => <div key={i} className="h-14 skeleton rounded-xl" />)}
          </div>
        ) : bundles.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              >
              <Bell className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{t("noBundles")}</p>
          </div>
        ) : (
          <div className="vf-divide">
            {bundles.map(b => (
              <div key={b.id} className="flex items-center gap-4 px-5 py-4 vf-row">
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  b.is_active ? "bg-indigo-500/10" : "bg-gray-500/10"
                }`}>
                  <Bell className={`h-4 w-4 ${b.is_active ? "text-indigo-400" : "vf-text-m"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1">{b.bundle_name}</p>
                  <p className="text-xs vf-text-m">
                    {b.delivery_channel} · {b.schedule}
                    {b.digest_time ? ` @ ${b.digest_time}` : ""}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {b.event_types.slice(0, 3).map(ev => (
                      <span key={ev} className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400">
                        {ev}
                      </span>
                    ))}
                    {b.event_types.length > 3 && (
                      <span className="text-[11px] vf-text-m">+{b.event_types.length - 3}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => handleToggle(b)}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      b.is_active
                        ? "text-emerald-400 hover:bg-emerald-500/10"
                        : "vf-text-m hover:vf-text-1"
                    }`}>
                    {b.is_active
                      ? <><CheckCircle2 className="h-3.5 w-3.5" />{t("active")}</>
                      : <><XCircle className="h-3.5 w-3.5" />{t("inactive")}</>}
                  </button>
                  <button onClick={() => startEdit(b)}
                    className="flex h-8 w-8 items-center justify-center rounded-lg vf-text-m hover:vf-text-1 hover:bg-indigo-500/10 transition-colors">
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button onClick={() => handleDelete(b.id)}
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-red-400 hover:bg-red-500/10 transition-colors">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
