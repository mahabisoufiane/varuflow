"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { CreditCard, CheckCircle, XCircle, Settings, Zap, Globe, ChevronRight } from "lucide-react";
import styles from "./page.module.scss";

interface ProviderConfig {
  provider: string;
  is_enabled: boolean;
  merchant_id: string | null;
  config_json: Record<string, string> | null;
}

interface PaymentSession {
  id: string;
  provider: string;
  amount: number;
  currency: string;
  status: string;
  invoice_id: string | null;
  customer_email: string | null;
  created_at: string;
  redirect_url: string | null;
}

const PROVIDERS = [
  { id: "klarna",   name: "Klarna",    flag: "🇸🇪",  markets: "SE, NO, DK", desc: "Buy now, pay later — dominant in Scandinavia" },
  { id: "swish",    name: "Swish",     flag: "🇸🇪",  markets: "SE",          desc: "Swedish mobile payment via Bankgirot" },
  { id: "vipps",    name: "Vipps",     flag: "🇳🇴",  markets: "NO",          desc: "Norwegian mobile payment app" },
  { id: "tabby",    name: "Tabby",     flag: "🌍",   markets: "AE, SA, KW",  desc: "BNPL for MENA markets" },
  { id: "tamara",   name: "Tamara",    flag: "🌍",   markets: "SA, AE",      desc: "BNPL for Saudi Arabia & UAE" },
  { id: "mada",     name: "mada",      flag: "🇸🇦",  markets: "SA",          desc: "Saudi Arabia national payment network" },
  { id: "knet",     name: "KNET",      flag: "🇰🇼",  markets: "KW",          desc: "Kuwait national payment debit network" },
];

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  authorized: "bg-blue-100 text-blue-700",
  captured: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
  refunded: "bg-purple-100 text-purple-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending:    "statusPending",
  authorized: "statusAuthorized",
  captured:   "statusCaptured",
  failed:     "statusFailed",
  cancelled:  "statusCancelled",
  refunded:   "statusRefunded",
};

export default function LocalPaymentsPage() {
  const [configs, setConfigs] = useState<Record<string, ProviderConfig>>({});
  const [sessions, setSessions] = useState<PaymentSession[]>([]);
  const [tab, setTab] = useState<"providers" | "sessions">("providers");
  const [editing, setEditing] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ merchant_id: "", api_key: "", config_json: "{}" });
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);
  useEffect(() => { if (tab === "sessions") loadSessions(); }, [tab]);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get("/api/local-payments/config");
      const map: Record<string, ProviderConfig> = {};
      (Array.isArray(data) ? data : []).forEach((c: ProviderConfig) => { map[c.provider] = c; });
      setConfigs(map);
    } catch { toast.error("Failed to load payment configs"); }
    finally { setLoading(false); }
  }

  async function loadSessions() {
    try {
      const data = await api.get("/api/local-payments/sessions?limit=50");
      setSessions(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load sessions"); }
  }

  async function toggleProvider(provider: string, current: boolean) {
    try {
      await api.patch(`/api/local-payments/config/${provider}`, { is_enabled: !current });
      setConfigs(prev => ({
        ...prev,
        [provider]: { ...prev[provider], provider, is_enabled: !current },
      }));
      toast.success(current ? "Provider disabled" : "Provider enabled");
    } catch { toast.error("Failed to update"); }
  }

  async function saveConfig() {
    if (!editing) return;
    try {
      let parsed_config: Record<string, string> = {};
      try { parsed_config = JSON.parse(editForm.config_json); } catch {}
      await api.patch(`/api/local-payments/config/${editing}`, {
        merchant_id: editForm.merchant_id || null,
        config_json: Object.keys(parsed_config).length ? parsed_config : null,
      });
      await load();
      setEditing(null);
      toast.success("Configuration saved");
    } catch { toast.error("Failed to save configuration"); }
  }

  function startEdit(provider: string) {
    const cfg = configs[provider];
    setEditForm({
      merchant_id: cfg?.merchant_id ?? "",
      api_key: "",
      config_json: JSON.stringify(cfg?.config_json ?? {}, null, 2),
    });
    setEditing(provider);
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2"><Globe size={22} /> Local Payment Methods</h1>
        <p className="text-sm text-gray-500 mt-0.5">Enable and configure region-specific payment providers for your customer portal</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {(["providers", "sessions"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${tab === t ? "border-b-2 border-[#1a2332] text-[#1a2332]" : "text-gray-500"}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── Providers tab ─────────────────────────────────────────────── */}
      {tab === "providers" && (
        <div className="grid gap-4">
          {PROVIDERS.map(p => {
            const cfg = configs[p.id];
            const isEnabled = cfg?.is_enabled ?? false;
            return (
              <div key={p.id} className={`bg-white border-2 rounded-xl p-4 ${isEnabled ? "border-green-200" : "border-gray-200"}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="text-2xl">{p.flag}</div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{p.name}</span>
                        <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{p.markets}</span>
                        {isEnabled && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle size={12} /> Active</span>}
                      </div>
                      <p className="text-sm text-gray-500 mt-0.5">{p.desc}</p>
                      {cfg?.merchant_id && <p className="text-xs text-gray-400 mt-1">Merchant ID: {cfg.merchant_id}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => startEdit(p.id)}
                      className="p-1.5 rounded hover:bg-gray-100 text-gray-500" title="Configure">
                      <Settings size={15} />
                    </button>
                    <button
                      onClick={() => toggleProvider(p.id, isEnabled)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        isEnabled
                          ? "bg-red-50 text-red-600 hover:bg-red-100"
                          : "bg-green-50 text-green-600 hover:bg-green-100"
                      }`}>
                      {isEnabled ? "Disable" : "Enable"}
                    </button>
                  </div>
                </div>

                {/* Config editor */}
                {editing === p.id && (
                  <div className="mt-4 border-t pt-4 space-y-3">
                    <div>
                      <label className="block text-xs font-medium mb-1">Merchant ID / Account number</label>
                      <input value={editForm.merchant_id} onChange={e => setEditForm(f => ({ ...f, merchant_id: e.target.value }))}
                        className="input w-full" placeholder={`Your ${p.name} merchant ID`} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium mb-1">Additional config (JSON)</label>
                      <textarea value={editForm.config_json} onChange={e => setEditForm(f => ({ ...f, config_json: e.target.value }))}
                        rows={4} className="input w-full font-mono text-xs"
                        placeholder='{"environment": "production", "locale": "sv-SE"}' />
                      <p className="text-xs text-gray-400 mt-1">API keys are stored encrypted. Enter your credentials securely.</p>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={saveConfig} className="btn-primary">Save</button>
                      <button onClick={() => setEditing(null)} className="btn-secondary">Cancel</button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Sessions tab ─────────────────────────────────────────────── */}
      {tab === "sessions" && (
        <div className="bg-white border rounded-lg overflow-hidden">
          {sessions.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <CreditCard size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No payment sessions yet.</p>
              <p className="text-xs mt-1">Sessions are created when customers initiate checkout via the portal.</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Provider", "Amount", "Customer", "Status", "Created"].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <span className="font-medium capitalize">{s.provider}</span>
                    </td>
                    <td className="px-4 py-2 font-mono">
                      {s.amount.toFixed(2)} {s.currency}
                    </td>
                    <td className="px-4 py-2 text-gray-500">{s.customer_email ?? "—"}</td>
                    <td className="px-4 py-2">
                      <span className={styles[STATUS_MODULE[s.status] ?? "statusPending"]}>
                        {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-400">{new Date(s.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
