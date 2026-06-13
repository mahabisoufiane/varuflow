"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { RefreshCw, Smartphone, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface AppConfig {
  app_name: string;
  primary_color: string;
  secondary_color: string;
  logo_url: string;
  welcome_message: string;
  booking_enabled: boolean;
  loyalty_enabled: boolean;
  notifications_enabled: boolean;
}

interface AppStats {
  total_devices: number;
  by_platform: { ios: number; android: number; web: number };
  active_tokens: number;
}

interface PushToken {
  id: string;
  customer_id: string;
  token: string;
  platform: string;
  app_version: string;
  last_seen_at: string;
}

const PLATFORM_BADGE: Record<string, string> = {
  ios: "bg-gray-100 text-gray-700",
  android: "bg-green-100 text-green-700",
  web: "bg-blue-100 text-blue-700",
};

export default function CustomerAppConfigPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [config, setConfig] = useState<AppConfig>({
    app_name: "",
    primary_color: "#1a2332",
    secondary_color: "#ffffff",
    logo_url: "",
    welcome_message: "",
    booking_enabled: false,
    loyalty_enabled: false,
    notifications_enabled: false,
  });
  const [stats, setStats] = useState<AppStats | null>(null);
  const [tokens, setTokens] = useState<PushToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showTokenForm, setShowTokenForm] = useState(false);
  const [tokenForm, setTokenForm] = useState({
    customer_id: "",
    token: "",
    platform: "ios",
    app_version: "",
  });

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }

      const headers = { Authorization: `Bearer ${token}` };
      const [cfgRes, statsRes, tokRes] = await Promise.all([
        fetch(apiUrl("/api/customer-app/config"), { headers }),
        fetch(apiUrl("/api/customer-app/stats"), { headers }),
        fetch(apiUrl("/api/customer-app/push-tokens"), { headers }),
      ]);
      if (cfgRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (cfgRes.ok) setConfig(await cfgRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (tokRes.ok) setTokens(await tokRes.json());
    } catch {
      toast.error("Failed to load customer app config");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function saveConfig() {
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/customer-app/config"), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(config),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save config");
        return;
      }
      toast.success("Config saved");
    } catch {
      toast.error("Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  async function deleteToken(id: string) {
    setActionLoading(id);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/customer-app/push-tokens/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete token");
        return;
      }
      toast.success("Token deleted");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function registerToken() {
    if (!tokenForm.customer_id.trim() || !tokenForm.token.trim()) {
      toast.error("Customer ID and token are required");
      return;
    }
    setActionLoading("register");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/customer-app/push-tokens"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(tokenForm),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to register token");
        return;
      }
      toast.success("Push token registered");
      setShowTokenForm(false);
      setTokenForm({ customer_id: "", token: "", platform: "ios", app_version: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const inputCls = "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]";

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Customer App</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configure your branded mobile app and manage push notification tokens.
          </p>
        </div>
      </div>

      {/* Config card */}
      <div className="rounded-xl border bg-white shadow-sm p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-900">App Configuration</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">App Name</label>
            <input value={config.app_name} onChange={(e) => setConfig((c) => ({ ...c, app_name: e.target.value }))}
              placeholder="My Loyalty App" className={inputCls} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Logo URL</label>
            <input value={config.logo_url} onChange={(e) => setConfig((c) => ({ ...c, logo_url: e.target.value }))}
              placeholder="https://..." className={inputCls} />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Primary Color</label>
            <div className="flex gap-2 items-center">
              <input type="color" value={config.primary_color}
                onChange={(e) => setConfig((c) => ({ ...c, primary_color: e.target.value }))}
                className="h-9 w-12 rounded border border-gray-300 cursor-pointer" />
              <span className="text-sm text-gray-600 font-mono">{config.primary_color}</span>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Secondary Color</label>
            <div className="flex gap-2 items-center">
              <input type="color" value={config.secondary_color}
                onChange={(e) => setConfig((c) => ({ ...c, secondary_color: e.target.value }))}
                className="h-9 w-12 rounded border border-gray-300 cursor-pointer" />
              <span className="text-sm text-gray-600 font-mono">{config.secondary_color}</span>
            </div>
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-700">Welcome Message</label>
          <textarea value={config.welcome_message}
            onChange={(e) => setConfig((c) => ({ ...c, welcome_message: e.target.value }))}
            rows={3} placeholder="Welcome to our app…"
            className={inputCls} />
        </div>
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-700">Feature Toggles</p>
          {(["booking_enabled", "loyalty_enabled", "notifications_enabled"] as const).map((key) => (
            <label key={key} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={config[key]}
                onChange={(e) => setConfig((c) => ({ ...c, [key]: e.target.checked }))}
                className="h-4 w-4 rounded border-gray-300" />
              <span className="text-sm text-gray-700 capitalize">{key.replace(/_/g, " ")}</span>
            </label>
          ))}
        </div>
        <div>
          <Button onClick={saveConfig} disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
            {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
            Save Config
          </Button>
        </div>
      </div>

      {/* Stats card */}
      {stats && (
        <div className="rounded-xl border bg-white shadow-sm p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-900">App Stats</h2>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats.total_devices}</p>
              <p className="text-xs text-muted-foreground">Registered Devices</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats.active_tokens}</p>
              <p className="text-xs text-muted-foreground">Active Tokens</p>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(stats.by_platform).map(([platform, count]) => (
              <span key={platform}
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${PLATFORM_BADGE[platform] ?? "bg-gray-100 text-gray-700"}`}>
                {platform}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Push Tokens */}
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900">Push Tokens</h2>
          <Button onClick={() => setShowTokenForm((s) => !s)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
            <Smartphone className="h-4 w-4" /> Register Token
          </Button>
        </div>

        {showTokenForm && (
          <div className="px-5 py-4 border-b border-gray-100 space-y-3 bg-gray-50">
            <h3 className="text-xs font-semibold text-gray-700">Register Push Token</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Customer ID *</label>
                <input value={tokenForm.customer_id}
                  onChange={(e) => setTokenForm((f) => ({ ...f, customer_id: e.target.value }))}
                  placeholder="UUID" className={inputCls} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Token *</label>
                <input value={tokenForm.token}
                  onChange={(e) => setTokenForm((f) => ({ ...f, token: e.target.value }))}
                  placeholder="Push notification token" className={inputCls} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Platform</label>
                <select value={tokenForm.platform}
                  onChange={(e) => setTokenForm((f) => ({ ...f, platform: e.target.value }))}
                  className={inputCls}>
                  <option value="ios">iOS</option>
                  <option value="android">Android</option>
                  <option value="web">Web</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">App Version</label>
                <input value={tokenForm.app_version}
                  onChange={(e) => setTokenForm((f) => ({ ...f, app_version: e.target.value }))}
                  placeholder="1.0.0" className={inputCls} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowTokenForm(false)}>Cancel</Button>
              <Button disabled={actionLoading === "register"} onClick={registerToken}
                className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {actionLoading === "register" ? "Registering…" : "Register"}
              </Button>
            </div>
          </div>
        )}

        {tokens.length === 0 ? (
          <div className="py-10 text-center text-sm text-muted-foreground">No push tokens registered</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {tokens.map((t) => (
              <div key={t.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1 min-w-0 space-y-0.5">
                  <p className="text-xs font-mono text-gray-700 truncate">{t.customer_id.slice(0, 8)}…</p>
                  <p className="text-xs text-muted-foreground">v{t.app_version}</p>
                </div>
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${PLATFORM_BADGE[t.platform] ?? "bg-gray-100 text-gray-700"}`}>
                  {t.platform}
                </span>
                <p className="text-xs text-muted-foreground hidden sm:block">
                  {t.last_seen_at ? new Date(t.last_seen_at).toLocaleDateString() : "—"}
                </p>
                <Button variant="ghost" size="sm" disabled={actionLoading === t.id}
                  onClick={() => deleteToken(t.id)}>
                  {actionLoading === t.id
                    ? <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    : <Trash2 className="h-3.5 w-3.5 text-red-500" />}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
