"use client";

/**
 * Fixed Asset Register
 *
 * Wires:
 *   GET    /api/accounting/assets
 *   POST   /api/accounting/assets
 *   PATCH  /api/accounting/assets/{id}
 *   POST   /api/accounting/assets/{id}/depreciate?period=YYYY-MM
 *   POST   /api/accounting/assets/{id}/dispose
 *   POST   /api/accounting/assets/{id}/revalue
 *   GET    /api/accounting/assets/{id}/schedule
 *   GET    /api/accounting/assets/report/depreciation-schedule
 *   GET    /api/accounting/assets/export/sie4
 */
import { useCallback, useEffect, useState } from "react";
import {
  Landmark, Loader2, Plus, RefreshCw, TrendingDown,
  FileSpreadsheet, X, BarChart2, RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

// ─── Types ──────────────────────────────────────────────────────────────────

interface DepreciationEntry {
  id: string;
  period: string;
  amount: string;
  journal_entry_id: string | null;
}

interface Asset {
  id: string;
  name: string;
  category: string;
  acquisition_date: string;
  acquisition_cost: string;
  salvage_value: string;
  useful_life_years: number;
  depreciation_method: string;
  current_book_value: string;
  account_code: string;
  notes: string | null;
  supplier: string | null;
  purchase_order_id: string | null;
  expense_id: string | null;
  is_disposed: boolean;
  disposed_at: string | null;
  disposal_proceeds: string | null;
  depreciations: DepreciationEntry[];
}

interface ScheduleLine {
  period: string;
  depreciation: string;
  book_value_after: string;
}

interface OrgScheduleLine {
  asset_id: string;
  asset_name: string;
  category: string;
  period: string;
  depreciation: string;
  book_value_after: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CATEGORIES = ["BUILDING", "EQUIPMENT", "VEHICLE", "IP", "OTHER"];
const METHODS    = ["STRAIGHT_LINE", "DECLINING_BALANCE"];

const METHOD_LABEL: Record<string, string> = {
  STRAIGHT_LINE:     "Straight-line",
  DECLINING_BALANCE: "Declining balance",
};

const CATEGORY_COLOR: Record<string, string> = {
  BUILDING:  "bg-indigo-500/20 text-indigo-300",
  EQUIPMENT: "bg-sky-500/20 text-sky-300",
  VEHICLE:   "bg-emerald-500/20 text-emerald-300",
  IP:        "bg-purple-500/20 text-purple-300",
  OTHER:     "bg-gray-500/20 text-gray-300",
};

const CATEGORY_MODULE: Record<string, keyof typeof styles> = {
  BUILDING:  "categoryBuilding",
  EQUIPMENT: "categoryEquipment",
  VEHICLE:   "categoryVehicle",
  IP:        "categoryIP",
  OTHER:     "categoryOther",
};

function totalNBV(assets: Asset[]) {
  return assets.reduce((s, a) => s + Number(a.current_book_value), 0);
}

function depreciation_pct(a: Asset) {
  const cost = Number(a.acquisition_cost);
  const book = Number(a.current_book_value);
  if (cost === 0) return 0;
  return Math.round(((cost - book) / cost) * 100);
}

// ─── Schedule Report Modal ───────────────────────────────────────────────────

function ScheduleReportModal({ onClose }: { onClose: () => void }) {
  const today = new Date();
  const [fromDate, setFromDate] = useState(`${today.getFullYear()}-01-01`);
  const [toDate, setToDate]     = useState(`${today.getFullYear()}-12-01`);
  const [lines, setLines]       = useState<OrgScheduleLine[] | null>(null);
  const [loading, setLoading]   = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.get<OrgScheduleLine[]>(
        `/api/accounting/assets/report/depreciation-schedule?from_date=${fromDate}&to_date=${toDate}`
      );
      setLines(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load schedule");
    } finally { setLoading(false); }
  };

  // Group lines by period for summary
  const byPeriod: Record<string, OrgScheduleLine[]> = {};
  for (const l of lines ?? []) {
    (byPeriod[l.period.slice(0, 7)] ??= []).push(l);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="vf-section w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-indigo-400" />
            <p className="font-semibold vf-text-1 text-sm">Depreciation Schedule Report</p>
          </div>
          <button onClick={onClose} className="vf-btn-ghost p-1"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-4 flex gap-3 items-end border-b border-white/10">
          <div>
            <label className="text-xs vf-text-m block mb-1">From</label>
            <input type="month" value={fromDate.slice(0, 7)}
              onChange={e => setFromDate(e.target.value + "-01")}
              className="vf-input text-sm" />
          </div>
          <div>
            <label className="text-xs vf-text-m block mb-1">To</label>
            <input type="month" value={toDate.slice(0, 7)}
              onChange={e => setToDate(e.target.value + "-01")}
              className="vf-input text-sm" />
          </div>
          <button onClick={load} className="vf-btn text-xs px-4 py-2">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Generate"}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {lines === null && !loading && (
            <p className="text-center vf-text-m text-sm py-8">Set a date range and click Generate</p>
          )}
          {loading && (
            <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          )}
          {lines && !loading && lines.length === 0 && (
            <p className="text-center vf-text-m text-sm py-8">No depreciation in this period</p>
          )}
          {lines && !loading && lines.length > 0 && (
            <div className="space-y-4">
              {/* Summary row */}
              <div className="vf-section p-3 flex justify-between items-center">
                <span className="text-xs vf-text-m">{lines.length} entries across {Object.keys(byPeriod).length} months</span>
                <span className="text-sm font-mono font-bold vf-text-1">
                  Total: {fmt(lines.reduce((s, l) => s + Number(l.depreciation), 0))}
                </span>
              </div>

              {/* Table */}
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left py-2 vf-text-m font-medium">Period</th>
                    <th className="text-left py-2 vf-text-m font-medium">Asset</th>
                    <th className="text-left py-2 vf-text-m font-medium">Category</th>
                    <th className="text-right py-2 vf-text-m font-medium">Depreciation</th>
                    <th className="text-right py-2 vf-text-m font-medium">Book Value After</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                      <td className="py-1.5 vf-text-m">{l.period.slice(0, 7)}</td>
                      <td className="py-1.5 vf-text-1">{l.asset_name}</td>
                      <td className="py-1.5">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${CATEGORY_COLOR[l.category] ?? "bg-gray-500/20 text-gray-300"}`}>
                          {l.category}
                        </span>
                      </td>
                      <td className="py-1.5 font-mono text-right text-rose-400">-{fmt(l.depreciation)}</td>
                      <td className="py-1.5 font-mono text-right vf-text-1">{fmt(l.book_value_after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Revalue Modal ───────────────────────────────────────────────────────────

function RevalueModal({ asset, onClose, onDone }: { asset: Asset; onClose: () => void; onDone: () => void }) {
  const [newBv, setNewBv]     = useState(asset.current_book_value);
  const [reason, setReason]   = useState("");
  const [revDate, setRevDate] = useState(new Date().toISOString().slice(0, 10));
  const [saving, setSaving]   = useState(false);

  const diff = Number(newBv) - Number(asset.current_book_value);

  const submit = async () => {
    if (!newBv || isNaN(Number(newBv))) { toast.error("Enter a valid book value"); return; }
    setSaving(true);
    try {
      await api.post(`/api/accounting/assets/${asset.id}/revalue`, {
        revaluation_date: revDate,
        new_book_value: parseFloat(newBv),
        reason: reason || undefined,
      });
      toast.success("Revaluation posted");
      onDone();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="vf-section w-full max-w-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <p className="font-semibold vf-text-1 text-sm">Revalue Asset</p>
          <button onClick={onClose} className="vf-btn-ghost p-1"><X className="w-4 h-4" /></button>
        </div>

        <div className="text-xs vf-text-m space-y-1">
          <p>{asset.name}</p>
          <p>Current book value: <span className="font-mono vf-text-1">{fmt(asset.current_book_value)}</span></p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs vf-text-m block mb-1">Revaluation Date</label>
            <input type="date" value={revDate} onChange={e => setRevDate(e.target.value)}
              className="vf-input text-sm w-full" />
          </div>
          <div>
            <label className="text-xs vf-text-m block mb-1">New Book Value</label>
            <input type="number" value={newBv} onChange={e => setNewBv(e.target.value)}
              className="vf-input text-sm w-full" min="0" step="0.01" />
          </div>
          <div>
            <label className="text-xs vf-text-m block mb-1">Reason (optional)</label>
            <input type="text" value={reason} onChange={e => setReason(e.target.value)}
              className="vf-input text-sm w-full" placeholder="e.g. Independent valuation report" />
          </div>
        </div>

        {newBv && !isNaN(Number(newBv)) && Number(newBv) !== Number(asset.current_book_value) && (
          <div className={`text-xs px-3 py-2 rounded ${diff > 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
            {diff > 0 ? "▲ Upward revaluation:" : "▼ Downward revaluation:"}
            {" "}{fmt(Math.abs(diff))} will be {diff > 0 ? "credited to reserve (3900)" : "debited to loss (7900)"}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
          <button onClick={submit} disabled={saving} className="vf-btn text-xs px-4 py-1.5">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Post Revaluation"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function AssetsPage() {
  const [assets, setAssets]             = useState<Asset[]>([]);
  const [loading, setLoading]           = useState(true);
  const [selected, setSelected]         = useState<Asset | null>(null);
  const [schedule, setSchedule]         = useState<ScheduleLine[] | null>(null);
  const [schedLoading, setSchedLoading] = useState(false);
  const [showCreate, setShowCreate]     = useState(false);
  const [showDispose, setShowDispose]   = useState(false);
  const [showRevalue, setShowRevalue]   = useState(false);
  const [showReport, setShowReport]     = useState(false);
  const [includeDisposed, setIncludeDisposed] = useState(false);
  const [depPeriod, setDepPeriod]       = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [disposeData, setDisposeData] = useState({
    disposed_at: new Date().toISOString().slice(0, 10),
    disposal_proceeds: "0",
  });

  const [form, setForm] = useState({
    name: "", category: "EQUIPMENT",
    acquisition_date: new Date().toISOString().slice(0, 10),
    acquisition_cost: "", salvage_value: "0", useful_life_years: "5",
    depreciation_method: "STRAIGHT_LINE", account_code: "1710",
    notes: "", supplier: "",
    purchase_order_id: "", expense_id: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<Asset[]>(`/api/accounting/assets?include_disposed=${includeDisposed}`);
      setAssets(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load assets");
    } finally { setLoading(false); }
  }, [includeDisposed]);

  useEffect(() => { load(); }, [load]);

  const loadSchedule = async (id: string) => {
    setSchedLoading(true);
    try {
      const data = await api.get<ScheduleLine[]>(`/api/accounting/assets/${id}/schedule`);
      setSchedule(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load schedule");
    } finally { setSchedLoading(false); }
  };

  const handleCreate = async () => {
    if (!form.name || !form.acquisition_cost) { toast.error("Name and cost required"); return; }
    try {
      await api.post("/api/accounting/assets", {
        name: form.name,
        category: form.category,
        acquisition_date: form.acquisition_date,
        acquisition_cost: parseFloat(form.acquisition_cost),
        salvage_value: parseFloat(form.salvage_value) || 0,
        useful_life_years: parseInt(form.useful_life_years),
        depreciation_method: form.depreciation_method,
        account_code: form.account_code,
        notes: form.notes || undefined,
        supplier: form.supplier || undefined,
        purchase_order_id: form.purchase_order_id || undefined,
        expense_id: form.expense_id || undefined,
      });
      toast.success("Asset created");
      setShowCreate(false);
      setForm(prev => ({ ...prev, name: "", acquisition_cost: "", supplier: "", purchase_order_id: "", expense_id: "", notes: "" }));
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleDepreciate = async () => {
    if (!selected) return;
    try {
      await api.post(`/api/accounting/assets/${selected.id}/depreciate?period=${depPeriod}`, {});
      toast.success(`Depreciation posted for ${depPeriod}`);
      await load();
      const updated = (await api.get<Asset[]>(`/api/accounting/assets?include_disposed=${includeDisposed}`))
        .find(a => a.id === selected.id);
      if (updated) setSelected(updated);
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleDispose = async () => {
    if (!selected) return;
    try {
      await api.post(`/api/accounting/assets/${selected.id}/dispose`, {
        disposed_at: disposeData.disposed_at,
        disposal_proceeds: parseFloat(disposeData.disposal_proceeds) || 0,
      });
      toast.success("Asset disposed");
      setShowDispose(false);
      setSelected(null);
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleSIE4Export = () => {
    const url = api.downloadUrl("/api/accounting/assets/export/sie4");
    const a = document.createElement("a");
    a.href = url;
    a.download = `depreciation_sie4.se`;
    a.click();
  };

  const totalNbv = totalNBV(assets);

  return (
    <>
      {showReport  && <ScheduleReportModal onClose={() => setShowReport(false)} />}
      {showRevalue && selected && (
        <RevalueModal
          asset={selected}
          onClose={() => setShowRevalue(false)}
          onDone={async () => {
            setShowRevalue(false);
            await load();
            const updated = (await api.get<Asset[]>(`/api/accounting/assets?include_disposed=${includeDisposed}`))
              .find(a => a.id === selected.id);
            if (updated) setSelected(updated);
          }}
        />
      )}

      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Landmark className="w-6 h-6 text-indigo-400" />
            <div>
              <h1 className="text-xl font-bold vf-text-1">Fixed Asset Register</h1>
              <p className="text-xs vf-text-m mt-0.5">Track capital assets, depreciation, and disposals</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setShowReport(true)} className="vf-btn-ghost text-xs px-3 py-1.5">
              <BarChart2 className="w-3.5 h-3.5 mr-1.5 inline" />Schedule Report
            </button>
            <button onClick={handleSIE4Export} className="vf-btn-ghost text-xs px-3 py-1.5">
              <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5 inline" />SIE4 Export
            </button>
            <button onClick={load} className="vf-btn-ghost text-xs px-3 py-1.5">
              <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
            </button>
            <button onClick={() => setShowCreate(true)} className="vf-btn text-xs px-3 py-1.5">
              <Plus className="w-3.5 h-3.5 mr-1.5 inline" />Add Asset
            </button>
          </div>
        </div>

        {/* NBV Summary Banner */}
        {!loading && assets.length > 0 && (
          <div className="vf-section p-4 flex flex-wrap gap-6 items-center">
            <div>
              <p className="text-xs vf-text-m">Total Net Book Value</p>
              <p className="text-2xl font-bold font-mono vf-text-1">{fmt(totalNbv)}</p>
            </div>
            <div className="h-8 w-px bg-white/10 hidden sm:block" />
            <div>
              <p className="text-xs vf-text-m">Active Assets</p>
              <p className="text-lg font-bold vf-text-1">{assets.filter(a => !a.is_disposed).length}</p>
            </div>
            <div className="h-8 w-px bg-white/10 hidden sm:block" />
            <div>
              <p className="text-xs vf-text-m">Total Acquisition Cost</p>
              <p className="text-lg font-mono font-semibold vf-text-1">
                {fmt(assets.reduce((s, a) => s + Number(a.acquisition_cost), 0))}
              </p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <label className="flex items-center gap-1.5 cursor-pointer text-xs vf-text-m">
                <input type="checkbox" checked={includeDisposed}
                  onChange={e => setIncludeDisposed(e.target.checked)}
                  className="rounded" />
                Show disposed
              </label>
            </div>
          </div>
        )}

        {/* Create form */}
        {showCreate && (
          <div className="vf-section p-5 space-y-4">
            <p className="font-semibold vf-text-1">New Fixed Asset</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: "Name",                     key: "name",             type: "text"   },
                { label: "Acquisition Date",          key: "acquisition_date", type: "date"   },
                { label: "Cost (SEK)",                key: "acquisition_cost", type: "number" },
                { label: "Salvage Value",             key: "salvage_value",    type: "number" },
                { label: "Useful Life (years)",       key: "useful_life_years",type: "number" },
                { label: "BAS Account Code",          key: "account_code",     type: "text"   },
                { label: "Supplier (optional)",       key: "supplier",         type: "text"   },
                { label: "Purchase Order ID (opt.)", key: "purchase_order_id",type: "text"   },
                { label: "Expense ID (optional)",    key: "expense_id",       type: "text"   },
              ].map(f => (
                <div key={f.key}>
                  <label className="text-xs vf-text-m block mb-1">{f.label}</label>
                  <input type={f.type} value={(form as Record<string, string>)[f.key]}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    className="vf-input text-sm w-full" />
                </div>
              ))}
              <div>
                <label className="text-xs vf-text-m block mb-1">Category</label>
                <select value={form.category}
                  onChange={e => setForm(prev => ({ ...prev, category: e.target.value }))}
                  className="vf-input text-sm w-full">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs vf-text-m block mb-1">Depreciation Method</label>
                <select value={form.depreciation_method}
                  onChange={e => setForm(prev => ({ ...prev, depreciation_method: e.target.value }))}
                  className="vf-input text-sm w-full">
                  {METHODS.map(m => <option key={m} value={m}>{METHOD_LABEL[m]}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCreate(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
              <button onClick={handleCreate} className="vf-btn text-xs px-3 py-1.5">Save</button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {/* Asset list */}
          <div className="col-span-2">
            {loading ? (
              <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
            ) : (
              <div className="space-y-2">
                {assets.length === 0 && (
                  <div className="vf-section p-8 text-center vf-text-m text-sm">No assets yet. Add your first asset.</div>
                )}
                {assets.map(asset => (
                  <div
                    key={asset.id}
                    className={`vf-section p-4 cursor-pointer hover:ring-1 hover:ring-indigo-500/40 transition-all ${
                      selected?.id === asset.id ? "ring-1 ring-indigo-500/60" : ""
                    } ${asset.is_disposed ? "opacity-55" : ""}`}
                    onClick={() => { setSelected(asset); setSchedule(null); setShowDispose(false); setShowRevalue(false); }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <p className="font-semibold vf-text-1 text-sm">{asset.name}</p>
                          <span className={styles[CATEGORY_MODULE[asset.category] ?? "categoryOther"]}>
                            {asset.category}
                          </span>
                          {asset.is_disposed && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/20 text-rose-300">DISPOSED</span>
                          )}
                        </div>
                        <p className="text-xs vf-text-m">
                          {METHOD_LABEL[asset.depreciation_method]} · {asset.useful_life_years}y
                          {asset.supplier ? ` · ${asset.supplier}` : ""}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-mono font-bold vf-text-1">{fmt(asset.current_book_value)}</p>
                        <p className="text-xs vf-text-m">book value</p>
                      </div>
                    </div>
                    {/* Depreciation progress bar */}
                    <div className="mt-3">
                      <div className="flex justify-between text-xs vf-text-m mb-1">
                        <span>Depreciated: {depreciation_pct(asset)}%</span>
                        <span>Original: {fmt(asset.acquisition_cost)}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${asset.is_disposed ? "bg-gray-500" : "bg-indigo-500"}`}
                          style={{ width: `${depreciation_pct(asset)}%` }}
                        />
                      </div>
                    </div>
                    {asset.is_disposed && (
                      <p className="text-xs text-rose-400 mt-2">
                        Disposed {asset.disposed_at} · Proceeds: {fmt(asset.disposal_proceeds ?? 0)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Detail panel */}
          <div className="space-y-3">
            {selected ? (
              <>
                <div className="vf-section p-4 space-y-3">
                  <p className="font-semibold vf-text-1 text-sm">{selected.name}</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><p className="vf-text-m">Acquired</p><p className="vf-text-1 font-medium">{selected.acquisition_date}</p></div>
                    <div><p className="vf-text-m">Book Value</p><p className="vf-text-1 font-mono font-bold">{fmt(selected.current_book_value)}</p></div>
                    <div><p className="vf-text-m">Cost</p><p className="vf-text-1 font-mono">{fmt(selected.acquisition_cost)}</p></div>
                    <div><p className="vf-text-m">Salvage</p><p className="vf-text-1 font-mono">{fmt(selected.salvage_value)}</p></div>
                    <div><p className="vf-text-m">Useful Life</p><p className="vf-text-1">{selected.useful_life_years}y</p></div>
                    <div><p className="vf-text-m">Account</p><p className="vf-text-1 font-mono">{selected.account_code}</p></div>
                    <div><p className="vf-text-m">Method</p><p className="vf-text-1">{METHOD_LABEL[selected.depreciation_method]}</p></div>
                    {selected.supplier && (
                      <div><p className="vf-text-m">Supplier</p><p className="vf-text-1">{selected.supplier}</p></div>
                    )}
                    {selected.purchase_order_id && (
                      <div className="col-span-2"><p className="vf-text-m">Purchase Order</p>
                        <p className="vf-text-1 font-mono text-[11px] truncate">{selected.purchase_order_id}</p>
                      </div>
                    )}
                    {selected.expense_id && (
                      <div className="col-span-2"><p className="vf-text-m">Expense</p>
                        <p className="vf-text-1 font-mono text-[11px] truncate">{selected.expense_id}</p>
                      </div>
                    )}
                  </div>

                  {!selected.is_disposed && (
                    <>
                      {/* Run depreciation */}
                      <div className="space-y-2 pt-2 border-t border-white/10">
                        <p className="text-xs vf-text-m font-medium">Run Depreciation</p>
                        <div className="flex gap-2">
                          <input type="month" value={depPeriod}
                            onChange={e => setDepPeriod(e.target.value)}
                            className="vf-input text-xs flex-1" />
                          <button onClick={handleDepreciate} className="vf-btn text-xs px-3 py-1.5 shrink-0">Post</button>
                        </div>
                      </div>

                      {/* Revalue */}
                      <button
                        onClick={() => setShowRevalue(true)}
                        className="w-full vf-btn-ghost text-xs py-1.5 flex items-center justify-center gap-1.5"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />Revalue Asset
                      </button>

                      {/* Dispose */}
                      <button
                        onClick={() => setShowDispose(!showDispose)}
                        className="w-full vf-btn-ghost text-xs py-1.5 text-rose-400 hover:text-rose-300"
                      >
                        <TrendingDown className="w-3.5 h-3.5 mr-1.5 inline" />Dispose Asset
                      </button>

                      {showDispose && (
                        <div className="space-y-2 pt-2 border-t border-rose-500/20">
                          <p className="text-xs text-rose-400 font-medium">Record Disposal</p>
                          <div>
                            <label className="text-xs vf-text-m block mb-1">Disposal Date</label>
                            <input type="date" value={disposeData.disposed_at}
                              onChange={e => setDisposeData(p => ({ ...p, disposed_at: e.target.value }))}
                              className="vf-input text-xs w-full" />
                          </div>
                          <div>
                            <label className="text-xs vf-text-m block mb-1">Proceeds (0 = write-off)</label>
                            <input type="number" value={disposeData.disposal_proceeds}
                              placeholder="0.00"
                              onChange={e => setDisposeData(p => ({ ...p, disposal_proceeds: e.target.value }))}
                              className="vf-input text-xs w-full" />
                          </div>
                          <button onClick={handleDispose} className="w-full vf-btn text-xs py-1.5 bg-rose-500/20 text-rose-300">
                            Confirm Disposal
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Depreciation history */}
                {selected.depreciations.length > 0 && (
                  <div className="vf-section p-3">
                    <p className="text-xs font-medium vf-text-1 mb-2">
                      Depreciation History
                      <span className="vf-text-m font-normal ml-2">
                        Total posted: {fmt(selected.depreciations.reduce((s, d) => s + Number(d.amount), 0))}
                      </span>
                    </p>
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                      {selected.depreciations.slice().reverse().map(d => (
                        <div key={d.id} className="flex justify-between text-xs">
                          <span className="vf-text-m">{d.period.slice(0, 7)}</span>
                          <span className="font-mono text-rose-400">-{fmt(d.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Schedule */}
                <button
                  onClick={() => loadSchedule(selected.id)}
                  className="w-full vf-btn-ghost text-xs py-1.5"
                >
                  {schedLoading
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin inline" />
                    : schedule ? "Reload Schedule" : "View Full Schedule"}
                </button>

                {schedule && !schedLoading && (
                  <div className="vf-section p-3 max-h-64 overflow-y-auto">
                    <div className="flex justify-between mb-2">
                      <p className="text-xs font-medium vf-text-1">Depreciation Schedule</p>
                      <p className="text-xs vf-text-m">{schedule.length} periods</p>
                    </div>
                    <div className="space-y-0.5">
                      {schedule.map((l, i) => (
                        <div key={i} className="flex justify-between text-xs">
                          <span className="vf-text-m">{l.period.slice(0, 7)}</span>
                          <span className="font-mono text-rose-400/70">-{fmt(l.depreciation)}</span>
                          <span className="font-mono vf-text-1">{fmt(l.book_value_after)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="vf-section p-8 text-center vf-text-m text-sm">
                Select an asset to view details and run depreciation.
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
