"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";
import { Bell } from "lucide-react";

interface Prefs {
  invoice_created: boolean;
  payment_received: boolean;
  quote_sent: boolean;
  appointment_reminder: boolean;
  marketing: boolean;
}

const LABELS: Record<keyof Prefs, string> = {
  invoice_created: "New invoices",
  payment_received: "Payment receipts",
  quote_sent: "Quote notifications",
  appointment_reminder: "Appointment reminders",
  marketing: "Marketing & promotions",
};

export default function PortalNotificationPreferencesPage() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<Prefs>("/api/portal/notification-preferences")
      .then(setPrefs)
      .catch(() => toast.error("Failed to load preferences"));
  }, []);

  async function toggle(key: keyof Prefs) {
    if (!prefs) return;
    const updated = { ...prefs, [key]: !prefs[key] };
    setPrefs(updated);
    setSaving(true);
    try {
      await portalApi.patch("/api/portal/notification-preferences", { [key]: updated[key] });
    } catch {
      setPrefs(prefs); // revert
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Bell size={20} /> Notification Preferences
      </h1>
      <p className="text-sm text-gray-500">Choose what you want to be emailed about.</p>

      {!prefs ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <div className="bg-white border rounded-xl divide-y">
          {(Object.keys(LABELS) as (keyof Prefs)[]).map(key => (
            <div key={key} className="flex items-center justify-between px-4 py-3">
              <span className="text-sm font-medium">{LABELS[key]}</span>
              <button
                onClick={() => toggle(key)}
                disabled={saving}
                className={`relative inline-flex h-6 w-11 rounded-full transition-colors ${
                  prefs[key] ? "bg-indigo-600" : "bg-gray-200"
                } disabled:opacity-60`}
              >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform mt-0.5 ${
                  prefs[key] ? "translate-x-5" : "translate-x-0.5"
                }`} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
