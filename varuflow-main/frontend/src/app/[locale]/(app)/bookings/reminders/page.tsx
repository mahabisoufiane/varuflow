"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { Bell, Mail, MessageSquare, Phone, Save } from "lucide-react";

interface ReminderTemplate {
  channel: "sms" | "whatsapp" | "email";
  enabled: boolean;
  template: string;
  timings: string[];
}

interface ReminderSettings {
  templates: ReminderTemplate[];
}

const TIMING_OPTIONS = ["24h", "2h", "30min"];

const CHANNEL_ICONS: Record<string, React.ReactNode> = {
  sms: <Phone className="h-4 w-4" />,
  whatsapp: <MessageSquare className="h-4 w-4" />,
  email: <Mail className="h-4 w-4" />,
};

const CHANNEL_LABELS: Record<string, string> = {
  sms: "SMS",
  whatsapp: "WhatsApp",
  email: "Email",
};

export default function RemindersPage() {
  const t = useTranslations("bookings");
  const [settings, setSettings] = useState<ReminderSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get<ReminderSettings>(
          "/api/bookings/reminders/settings"
        );
        setSettings(data);
      } catch {
        toast.error(t("loadError"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function updateTemplate(
    channel: string,
    field: keyof ReminderTemplate,
    value: unknown
  ) {
    if (!settings) return;
    setSettings({
      ...settings,
      templates: settings.templates.map((tpl) =>
        tpl.channel === channel ? { ...tpl, [field]: value } : tpl
      ),
    });
  }

  function toggleTiming(channel: string, timing: string) {
    if (!settings) return;
    const tpl = settings.templates.find((t) => t.channel === channel);
    if (!tpl) return;
    const newTimings = tpl.timings.includes(timing)
      ? tpl.timings.filter((t) => t !== timing)
      : [...tpl.timings, timing];
    updateTemplate(channel, "timings", newTimings);
  }

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    try {
      await api.put("/api/bookings/reminders/settings", settings);
      toast.success(t("remindersSaved"));
    } catch {
      toast.error(t("remindersSaveError"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-current border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!settings) {
    return <p className="vf-text-m text-center py-12">{t("loadError")}</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="h-6 w-6 vf-text-1" />
          <h1 className="vf-text-1 text-2xl font-bold">{t("reminders")}</h1>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          {saving ? t("saving") : t("save")}
        </button>
      </div>

      <div className="space-y-4">
        {settings.templates.map((tpl) => (
          <div key={tpl.channel} className="vf-bg-card vf-border rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {CHANNEL_ICONS[tpl.channel]}
                <h2 className="vf-text-1 text-lg font-semibold">
                  {CHANNEL_LABELS[tpl.channel]}
                </h2>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={tpl.enabled}
                  onChange={(e) =>
                    updateTemplate(tpl.channel, "enabled", e.target.checked)
                  }
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-300 peer-checked:bg-primary rounded-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium vf-text-m mb-1">
                {t("template")}
              </label>
              <textarea
                value={tpl.template}
                onChange={(e) =>
                  updateTemplate(tpl.channel, "template", e.target.value)
                }
                rows={3}
                className="w-full rounded-md border px-3 py-2 text-sm vf-border"
                placeholder={t("templatePlaceholder")}
              />
              <p className="text-xs vf-text-m mt-1">
                {t("templateVars")}: {"{customer_name}"}, {"{service}"},{" "}
                {"{date}"}, {"{time}"}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium vf-text-m mb-2">
                {t("sendBefore")}
              </label>
              <div className="flex gap-2">
                {TIMING_OPTIONS.map((timing) => (
                  <button
                    key={timing}
                    onClick={() => toggleTiming(tpl.channel, timing)}
                    className={`rounded-md border px-3 py-1.5 text-sm vf-border ${
                      tpl.timings.includes(timing)
                        ? "bg-primary text-white border-primary"
                        : "hover:bg-accent"
                    }`}
                  >
                    {timing}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
