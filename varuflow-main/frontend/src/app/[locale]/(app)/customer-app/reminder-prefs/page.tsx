"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Bell, RefreshCw, AlertCircle, Edit2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface NotificationPrefs {
  customer_id: string;
  remind_1_day: boolean;
  remind_1_hour: boolean;
  channel_push: boolean;
  channel_email: boolean;
  channel_sms: boolean;
}

const DEFAULT_PREFS: Omit<NotificationPrefs, "customer_id"> = {
  remind_1_day: true,
  remind_1_hour: true,
  channel_push: true,
  channel_email: false,
  channel_sms: false,
};

function BoolDot({ value }: { value: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${value ? "bg-green-400" : "bg-gray-300"}`}
      title={value ? "Enabled" : "Disabled"}
    />
  );
}

interface ToggleRowProps {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}
function ToggleRow({ label, checked, onChange }: ToggleRowProps) {
  return (
    <label className="flex items-center justify-between cursor-pointer py-2.5">
      <span className="text-sm text-gray-800">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-[#1a2332] focus:ring-offset-2 ${
          checked ? "bg-[#1a2332]" : "bg-gray-200"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </label>
  );
}

export default function ReminderPrefsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [allPrefs, setAllPrefs] = useState<NotificationPrefs[]>([]);
  const [loadingAll, setLoadingAll] = useState(true);
  const [lookupId, setLookupId] = useState("");
  const [currentPrefs, setCurrentPrefs] = useState<NotificationPrefs | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function loadAll() {
    setLoadingAll(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const res = await fetch(apiUrl("/api/notification-prefs"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setAllPrefs(await res.json());
    } catch {
      toast.error("Failed to load preferences");
    } finally {
      setLoadingAll(false);
    }
  }

  useEffect(() => { loadAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function lookupCustomer() {
    if (!lookupId.trim()) { toast.error("Enter a customer ID"); return; }
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/notification-prefs/${lookupId.trim()}`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.status === 404) {
        // Pre-fill defaults for new customer
        setCurrentPrefs({ customer_id: lookupId.trim(), ...DEFAULT_PREFS });
        toast.info("No prefs found — showing defaults");
        return;
      }
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to load preferences");
        return;
      }
      setCurrentPrefs(await res.json());
    } catch {
      toast.error("Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function savePrefs() {
    if (!currentPrefs) return;
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/notification-prefs/${currentPrefs.customer_id}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          remind_1_day: currentPrefs.remind_1_day,
          remind_1_hour: currentPrefs.remind_1_hour,
          channel_push: currentPrefs.channel_push,
          channel_email: currentPrefs.channel_email,
          channel_sms: currentPrefs.channel_sms,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save preferences");
        return;
      }
      toast.success("Preferences saved");
      await loadAll();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  function editRow(pref: NotificationPrefs) {
    setLookupId(pref.customer_id);
    setCurrentPrefs({ ...pref });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function updatePref<K extends keyof Omit<NotificationPrefs, "customer_id">>(
    key: K,
    value: boolean
  ) {
    setCurrentPrefs((p) => (p ? { ...p, [key]: value } : p));
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Booking Reminder Preferences</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            View and override customer notification settings on their behalf.
          </p>
        </div>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-2.5 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
        <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-blue-800">
          Customers can configure their own reminder preferences from the mobile app. Use this page to
          view or override preferences on their behalf.
        </p>
      </div>

      {/* Lookup section */}
      <div className="rounded-xl border bg-white shadow-sm p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-900">Look Up Customer</h2>
        <div className="flex items-center gap-3">
          <input
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && lookupCustomer()}
            placeholder="Customer UUID"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <Button
            disabled={loading}
            onClick={lookupCustomer}
            className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-1"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
            Load
          </Button>
        </div>

        {/* Prefs editor */}
        {currentPrefs && (
          <div className="space-y-4 pt-2 border-t border-gray-100">
            <p className="text-xs text-muted-foreground">
              Editing prefs for <span className="font-mono text-gray-700">{currentPrefs.customer_id}</span>
            </p>

            {/* Timing */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                Reminder Timing
              </p>
              <div className="divide-y divide-gray-100">
                <ToggleRow
                  label="1 day before"
                  checked={currentPrefs.remind_1_day}
                  onChange={(v) => updatePref("remind_1_day", v)}
                />
                <ToggleRow
                  label="1 hour before"
                  checked={currentPrefs.remind_1_hour}
                  onChange={(v) => updatePref("remind_1_hour", v)}
                />
              </div>
            </div>

            {/* Channels */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                Notification Channels
              </p>
              <div className="divide-y divide-gray-100">
                <ToggleRow
                  label="Push notification"
                  checked={currentPrefs.channel_push}
                  onChange={(v) => updatePref("channel_push", v)}
                />
                <ToggleRow
                  label="Email"
                  checked={currentPrefs.channel_email}
                  onChange={(v) => updatePref("channel_email", v)}
                />
                <ToggleRow
                  label="SMS"
                  checked={currentPrefs.channel_sms}
                  onChange={(v) => updatePref("channel_sms", v)}
                />
              </div>
            </div>

            <Button
              disabled={saving}
              onClick={savePrefs}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-1"
            >
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
              Save Preferences
            </Button>
          </div>
        )}
      </div>

      {/* All prefs table */}
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">All Customer Preferences</h2>
          {loadingAll && <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>

        {!loadingAll && allPrefs.length === 0 ? (
          <div className="py-10 text-center">
            <Bell className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-gray-600">No preferences configured yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left">
                  <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Customer</th>
                  <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider text-center">1 Day</th>
                  <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider text-center">1 Hour</th>
                  <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider text-center">Push</th>
                  <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider text-center">Email</th>
                  <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider text-center">SMS</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {allPrefs.map((pref) => (
                  <tr key={pref.customer_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-gray-700">
                      {pref.customer_id.length > 20
                        ? pref.customer_id.slice(0, 20) + "…"
                        : pref.customer_id}
                    </td>
                    <td className="px-3 py-3 text-center"><BoolDot value={pref.remind_1_day} /></td>
                    <td className="px-3 py-3 text-center"><BoolDot value={pref.remind_1_hour} /></td>
                    <td className="px-3 py-3 text-center"><BoolDot value={pref.channel_push} /></td>
                    <td className="px-3 py-3 text-center"><BoolDot value={pref.channel_email} /></td>
                    <td className="px-3 py-3 text-center"><BoolDot value={pref.channel_sms} /></td>
                    <td className="px-3 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => editRow(pref)}
                        className="gap-1 text-xs"
                      >
                        <Edit2 className="h-3.5 w-3.5" /> Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
