"use client";

import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { Globe, Plus, Trash2, CheckCircle2, MapPin } from "lucide-react";

// Comprehensive list of IANA timezones relevant to the Nordic + EU market
const TIMEZONE_OPTIONS = [
  "Europe/Stockholm",
  "Europe/Oslo",
  "Europe/Copenhagen",
  "Europe/Helsinki",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Amsterdam",
  "Europe/Zurich",
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Asia/Tokyo",
  "Asia/Singapore",
];

interface OrgLocation {
  id: string;
  name: string;
  timezone: string;
  is_default: boolean;
  created_at: string;
}

export default function TimezonesPage() {
  const t      = useTranslations();
  const router = useRouter();
  const locale = useLocale();

  const [locations, setLocations] = useState<OrgLocation[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState({ name: "", timezone: "Europe/Stockholm" });

  useEffect(() => {
    api.get<OrgLocation[]>("/api/org/locations")
      .then(setLocations)
      .catch((e: Error) => {
        if (e.message.includes("session")) router.push(`/${locale}/auth/login`);
        else toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await api.post<OrgLocation>("/api/org/locations", form);
      setLocations(prev => [...prev, created]);
      setShowForm(false);
      setForm({ name: "", timezone: "Europe/Stockholm" });
      toast.success(t("locationAdded"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/api/org/locations/${id}`);
      setLocations(prev => prev.filter(l => l.id !== id));
      toast.success(t("locationDeleted"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleSetDefault(id: string) {
    try {
      await api.patch(`/api/org/locations/${id}`, { is_default: true });
      setLocations(prev =>
        prev.map(l => ({ ...l, is_default: l.id === id }))
      );
      toast.success(t("defaultUpdated"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  function guessLocalOffset(tz: string) {
    try {
      const now = new Date();
      const fmt = new Intl.DateTimeFormat("en", {
        timeZone: tz,
        timeZoneName: "short",
      });
      const parts = fmt.formatToParts(now);
      return parts.find(p => p.type === "timeZoneName")?.value ?? tz;
    } catch {
      return tz;
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("timezones")}</h1>
          <p className="text-xs vf-text-m mt-0.5">{t("timezonesDesc")}</p>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />{t("addLocation")}
        </button>
      </div>

      {showForm && (
        <div className="vf-section p-5">
          <h2 className="text-[13px] font-semibold vf-text-1 mb-4">{t("newLocation")}</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium vf-text-m block mb-1">{t("locationName")}</label>
              <input required value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Stockholm HQ" className="vf-input text-xs w-full" />
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-1">{t("timezone")}</label>
              <select value={form.timezone}
                onChange={e => setForm(f => ({ ...f, timezone: e.target.value }))}
                className="vf-input text-xs w-full">
                {TIMEZONE_OPTIONS.map(tz => (
                  <option key={tz} value={tz}>{tz} ({guessLocalOffset(tz)})</option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2 flex gap-2 justify-end">
              <button type="button" onClick={() => setShowForm(false)}
                className="rounded-lg px-4 py-2 text-xs font-medium vf-text-m"
                style={{ border: "1px solid var(--vf-border)" }}>
                {t("cancel")}
              </button>
              <button type="submit" className="vf-btn text-xs">{t("add")}</button>
            </div>
          </form>
        </div>
      )}

      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("orgLocations")}</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2].map(i => <div key={i} className="h-14 skeleton rounded-xl" />)}
          </div>
        ) : locations.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              style={{ background: "var(--vf-bg-elevated)" }}>
              <Globe className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{t("noLocations")}</p>
            <p className="text-xs vf-text-m mt-1">{t("addLocationToStart")}</p>
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--vf-divider)" }}>
            {locations.map(loc => (
              <div key={loc.id} className="flex items-center gap-4 px-5 py-4 vf-row">
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  loc.is_default ? "bg-indigo-500/10" : ""
                }`} style={!loc.is_default ? { background: "var(--vf-bg-elevated)" } : {}}>
                  {loc.is_default
                    ? <CheckCircle2 className="h-4 w-4 text-indigo-400" />
                    : <MapPin className="h-4 w-4 vf-text-m" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-[13px] font-semibold vf-text-1">{loc.name}</p>
                    {loc.is_default && (
                      <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400">
                        {t("default")}
                      </span>
                    )}
                  </div>
                  <p className="text-xs vf-text-m">{loc.timezone} · {guessLocalOffset(loc.timezone)}</p>
                </div>
                <div className="flex items-center gap-1">
                  {!loc.is_default && (
                    <button onClick={() => handleSetDefault(loc.id)}
                      className="rounded-lg px-3 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-500/10 transition-colors">
                      {t("setDefault")}
                    </button>
                  )}
                  <button onClick={() => handleDelete(loc.id)}
                    disabled={loc.is_default}
                    className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                      loc.is_default ? "opacity-30 cursor-not-allowed" : "text-red-400 hover:bg-red-500/10"
                    }`}>
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
