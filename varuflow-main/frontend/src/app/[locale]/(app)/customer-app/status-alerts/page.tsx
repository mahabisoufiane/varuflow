"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { Bell, RefreshCw, Trash2, CheckCircle2, Clock, XCircle, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface StatusAlert {
  id: string;
  alert_type: string;
  appointment_id: string | null;
  customer_id: string | null;
  delay_minutes: number | null;
  message: string;
  push_sent: boolean;
  created_at: string;
}

const ALERT_TYPE_CONFIG: Record<string, { label: string; color: string; Icon: React.ElementType }> = {
  running_late: { label: "Running Late", color: "bg-red-100 text-red-700",    Icon: Clock        },
  ready:        { label: "Ready",         color: "bg-green-100 text-green-700", Icon: CheckCircle2 },
  cancelled:    { label: "Cancelled",     color: "bg-gray-100 text-gray-600",   Icon: XCircle      },
  rescheduled:  { label: "Rescheduled",   color: "bg-amber-100 text-amber-700", Icon: RefreshCw    },
  completed:    { label: "Completed",     color: "bg-blue-100 text-blue-700",   Icon: CheckCircle2 },
  custom:       { label: "Custom",        color: "bg-purple-100 text-purple-700",Icon: Bell        },
};

const ALERT_TYPE_MODULE: Record<string, keyof typeof styles> = {
  running_late: "alertRunningLate",
  ready:        "alertReady",
  cancelled:    "alertCancelled",
  rescheduled:  "alertRescheduled",
  completed:    "alertCompleted",
  custom:       "alertCustom",
};

const MESSAGE_TEMPLATES: Record<string, string> = {
  running_late: "Your appointment is running {delay} minutes late. We apologize for the inconvenience.",
  ready:        "Your service is ready! Please head over when convenient.",
  cancelled:    "We're sorry, your appointment has been cancelled. Please contact us to reschedule.",
  completed:    "Your service is complete. Thank you for visiting us today!",
  rescheduled:  "Your appointment has been rescheduled. Please contact us for updated details.",
  custom:       "",
};

const QUICK_BUTTONS = [
  { label: "Running Late", type: "running_late" },
  { label: "Ready",        type: "ready"         },
  { label: "Cancelled",    type: "cancelled"      },
  { label: "Completed",    type: "completed"      },
];

export default function StatusAlertsPage() {
  const [alerts, setAlerts] = useState<StatusAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [form, setForm] = useState({
    alert_type: "running_late",
    appointment_id: "",
    customer_id: "",
    delay_minutes: "15",
    message: MESSAGE_TEMPLATES.running_late,
  });

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<StatusAlert[]>("/api/service-status/alerts");
      setAlerts(data);
    } catch {
      toast.error("Failed to load alerts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function applyQuickButton(type: string) {
    const template = MESSAGE_TEMPLATES[type] ?? "";
    const message = type === "running_late"
      ? template.replace("{delay}", form.delay_minutes || "15")
      : template;
    setForm((f) => ({ ...f, alert_type: type, message }));
  }

  function handleTypeChange(type: string) {
    const template = MESSAGE_TEMPLATES[type] ?? "";
    const message = type === "running_late"
      ? template.replace("{delay}", form.delay_minutes || "15")
      : template;
    setForm((f) => ({ ...f, alert_type: type, message }));
  }

  function handleDelayChange(delay: string) {
    setForm((f) => {
      const message = f.alert_type === "running_late"
        ? MESSAGE_TEMPLATES.running_late.replace("{delay}", delay || "15")
        : f.message;
      return { ...f, delay_minutes: delay, message };
    });
  }

  async function sendAlert() {
    if (!form.message.trim()) { toast.error("Message is required"); return; }
    setActionLoading("send");
    try {
      const body: Record<string, unknown> = {
        alert_type: form.alert_type,
        message: form.message,
        appointment_id: form.appointment_id || null,
        customer_id: form.customer_id || null,
      };
      if (form.alert_type === "running_late") {
        body.delay_minutes = parseInt(form.delay_minutes) || null;
      }
      await api.post("/api/service-status/alerts", body);
      toast.success("Alert sent");
      setForm({ alert_type: "running_late", appointment_id: "", customer_id: "", delay_minutes: "15", message: MESSAGE_TEMPLATES.running_late });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteAlert(id: string) {
    setActionLoading("del_" + id);
    try {
      await api.delete(`/api/service-status/alerts/${id}`);
      toast.success("Alert deleted");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Live Service Status</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage and send real-time service status alerts to customers.
          </p>
        </div>
      </div>

      {/* Info strip */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-800">
        Send proactive push notifications to customers before appointments — e.g. &quot;running 15 minutes late&quot;.
      </div>

      {/* Quick buttons */}
      <div className="flex flex-wrap gap-2">
        {QUICK_BUTTONS.map((btn) => (
          <button
            key={btn.type}
            type="button"
            onClick={() => applyQuickButton(btn.type)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium border transition-colors hover:opacity-80 ${
              ALERT_TYPE_CONFIG[btn.type]?.color ?? "bg-gray-100 text-gray-600"
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Create form */}
      <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Send Alert</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Alert Type</label>
            <select
              value={form.alert_type}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            >
              {Object.entries(ALERT_TYPE_CONFIG).map(([val, cfg]) => (
                <option key={val} value={val}>{cfg.label}</option>
              ))}
            </select>
          </div>
          {form.alert_type === "running_late" && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Delay (minutes)</label>
              <input
                type="number"
                value={form.delay_minutes}
                onChange={(e) => handleDelayChange(e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              />
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Appointment ID (optional)</label>
            <input
              value={form.appointment_id}
              onChange={(e) => setForm((f) => ({ ...f, appointment_id: e.target.value }))}
              placeholder="UUID"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Customer ID (optional)</label>
            <input
              value={form.customer_id}
              onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}
              placeholder="UUID"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-700">Message *</label>
          <textarea
            rows={3}
            value={form.message}
            onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
          />
        </div>
        <Button
          disabled={actionLoading === "send"}
          onClick={sendAlert}
          className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2"
        >
          {actionLoading === "send" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
          Send Alert
        </Button>
      </div>

      {/* Alerts list */}
      {loading && alerts.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <AlertCircle className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No alerts sent yet</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm">
          <div className="divide-y divide-gray-100">
            {alerts.map((alert) => {
              const cfg = ALERT_TYPE_CONFIG[alert.alert_type] ?? ALERT_TYPE_CONFIG.custom;
              const Icon = cfg.Icon;
              return (
                <div key={alert.id} className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={styles[ALERT_TYPE_MODULE[alert.alert_type] ?? "alertCustom"]}>
                        <Icon className="h-3 w-3" />
                        {cfg.label}
                      </span>
                      {alert.push_sent && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 text-green-700 px-2 py-0.5 text-xs">
                          <CheckCircle2 className="h-3 w-3" /> Push Sent
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 truncate mt-0.5">{alert.message}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {alert.appointment_id && `Appt: ${alert.appointment_id.slice(0, 8)}…`}
                      {alert.appointment_id && alert.customer_id && " · "}
                      {alert.customer_id && `Customer: ${alert.customer_id.slice(0, 8)}…`}
                      {" · "}{new Date(alert.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={actionLoading === "del_" + alert.id}
                    onClick={() => deleteAlert(alert.id)}
                    className="text-red-500 hover:text-red-700 hover:bg-red-50"
                  >
                    {actionLoading === "del_" + alert.id
                      ? <RefreshCw className="h-4 w-4 animate-spin" />
                      : <Trash2 className="h-4 w-4" />}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
