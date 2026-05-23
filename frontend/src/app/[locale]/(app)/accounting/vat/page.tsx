"use client";

/**
 * VAT Return Filing
 *
 * Supports SE (Skatteverket momsdeklaration), NO (Mva-melding), AE (UAE FTA).
 * New capabilities: PDF export, period locking, filing status tracking, audit trail.
 */
import { useCallback, useEffect, useState } from "react";
import { Download, FileText, ReceiptText, Lock, CheckCircle2, Clock, AlertCircle, ChevronRight, ChevronDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// ─── Types ─────────────────────────────────────────────────────────────────

interface VatBox     { label: string; description: string; amount: string; }
interface VatReturn  { country: string; from_date: string; to_date: string; boxes: VatBox[]; net_vat_payable: string; }
interface VatPeriod  { id: string; country: string; from_date: string; to_date: string; status: string; net_vat_payable: string; filed_at: string | null; reference: string | null; }
interface AuditLine  { id: string; source: string; date: string; reference: string; taxable_amount: string; vat_amount: string; tax_rate: string | null; }
interface AuditTrail { invoices: AuditLine[]; expenses: AuditLine[]; total_output_vat: string; total_input_vat: string; }

type Country = "SE" | "NO" | "AE";

// ─── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CUR_YEAR = new Date().getFullYear();
const YEARS = [CUR_YEAR, CUR_YEAR - 1, CUR_YEAR - 2];

const COUNTRY_INFO: Record<Country, { name: string; flag: string; freq: string }> = {
  SE:  { name: "Sweden — Skatteverket",  flag: "🇸🇪", freq: "Quarterly / Monthly" },
  NO:  { name: "Norway — Skatteetaten",  flag: "🇳🇴", freq: "Bi-monthly" },
  AE:  { name: "UAE — FTA Form 201",     flag: "🇦🇪", freq: "Quarterly" },
};

const QUARTERS = [
  { label: "Q1", from: "-01-01", to: "-03-31" },
  { label: "Q2", from: "-04-01", to: "-06-30" },
  { label: "Q3", from: "-07-01", to: "-09-30" },
  { label: "Q4", from: "-10-01", to: "-12-31" },
];

// ─── Audit trail ────────────────────────────────────────────────────────────

function AuditSection({ from, to, country }: { from: string; to: string; country: Country }) {
  const [open, setOpen] = useState(false);
  const [trail, setTrail] = useState<AuditTrail | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (trail) return;
    setLoading(true);
    try {
      const d = await api.get<AuditTrail>(
        `/api/accounting/vat-return/audit-trail?from=${from}&to=${to}&country=${country}`
      );
      setTrail(d);
    } catch {
      toast.error("Failed to load audit trail");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="vf-section overflow-hidden">
      <button onClick={toggle} className="w-full flex items-center justify-between px-5 py-3 hover:bg-white/5 transition-colors">
        <p className="text-sm font-medium vf-text-1">Audit trail — transactions included</p>
        {open ? <ChevronDown className="w-4 h-4 vf-text-m" /> : <ChevronRight className="w-4 h-4 vf-text-m" />}
      </button>
      {open && (
        <div className="border-t border-white/10 p-4 space-y-4">
          {loading && <div className="flex justify-center py-4"><Loader2 className="w-4 h-4 animate-spin vf-text-m" /></div>}
          {trail && (
            <>
              <div className="flex gap-6 text-xs vf-text-m">
                <span>Output VAT: <span className="font-semibold text-amber-300">{fmt(trail.total_output_vat)}</span></span>
                <span>Input VAT: <span className="font-semibold text-emerald-400">{fmt(trail.total_input_vat)}</span></span>
              </div>
              {trail.invoices.length > 0 && (
                <div>
                  <p className="text-xs vf-text-m uppercase tracking-wide mb-2">Invoice lines ({trail.invoices.length})</p>
                  <div className="border border-white/10 rounded-xl text-xs max-h-56 overflow-y-auto">
                    <div className="grid grid-cols-4 px-3 py-1.5 vf-text-m font-medium border-b border-white/10 sticky top-0 bg-[var(--vf-bg-elevated)]">
                      <span>Date</span><span>Reference</span><span className="text-right">Taxable</span><span className="text-right">VAT</span>
                    </div>
                    {trail.invoices.map((l) => (
                      <div key={l.id} className="grid grid-cols-4 px-3 py-1.5 border-b border-white/5 last:border-0">
                        <span className="vf-text-m">{l.date}</span>
                        <span className="vf-text-1 truncate">{l.reference}{l.tax_rate ? ` (${l.tax_rate}%)` : ""}</span>
                        <span className="text-right font-mono">{fmt(l.taxable_amount)}</span>
                        <span className="text-right font-mono text-amber-300">{fmt(l.vat_amount)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {trail.expenses.length > 0 && (
                <div>
                  <p className="text-xs vf-text-m uppercase tracking-wide mb-2">Expenses ({trail.expenses.length})</p>
                  <div className="border border-white/10 rounded-xl text-xs max-h-56 overflow-y-auto">
                    <div className="grid grid-cols-4 px-3 py-1.5 vf-text-m font-medium border-b border-white/10 sticky top-0 bg-[var(--vf-bg-elevated)]">
                      <span>Date</span><span>Description</span><span className="text-right">Gross</span><span className="text-right">Input VAT</span>
                    </div>
                    {trail.expenses.map((l) => (
                      <div key={l.id} className="grid grid-cols-4 px-3 py-1.5 border-b border-white/5 last:border-0">
                        <span className="vf-text-m">{l.date}</span>
                        <span className="vf-text-1 truncate">{l.reference}</span>
                        <span className="text-right font-mono">{fmt(l.taxable_amount)}</span>
                        <span className="text-right font-mono text-emerald-400">{fmt(l.vat_amount)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function VatReturnPage() {
  const [country, setCountry] = useState<Country>("SE");
  const [year, setYear] = useState(CUR_YEAR);
  const [selectedQ, setSelectedQ] = useState("Q1");
  const [useCustom, setUseCustom] = useState(false);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const [result, setResult] = useState<VatReturn | null>(null);
  const [loading, setLoading] = useState(false);
  const [periods, setPeriods] = useState<VatPeriod[]>([]);
  const [lockLoading, setLockLoading] = useState(false);
  const [fileModalId, setFileModalId] = useState<string | null>(null);
  const [fileRef, setFileRef] = useState("");
  const [fileSaving, setFileSaving] = useState(false);

  function getRange(): [string, string] {
    if (useCustom) return [customFrom, customTo];
    const q = QUARTERS.find((qq) => qq.label === selectedQ)!;
    return [`${year}${q.from}`, `${year}${q.to}`];
  }

  const [from, to] = getRange();

  const run = useCallback(async () => {
    if (!from || !to) return;
    setLoading(true);
    try {
      const data = await api.get<VatReturn>(
        `/api/accounting/vat-return?from=${from}&to=${to}&country=${country}&format=json`
      );
      setResult(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to calculate VAT return");
    } finally {
      setLoading(false);
    }
  }, [from, to, country]);

  const loadPeriods = useCallback(async () => {
    try {
      const p = await api.get<VatPeriod[]>(`/api/accounting/vat-return/periods?country=${country}`);
      setPeriods(p);
    } catch { /* silent */ }
  }, [country]);

  useEffect(() => { run(); loadPeriods(); }, [run, loadPeriods]);

  const downloadXml = () =>
    window.open(api.downloadUrl(`/api/accounting/vat-return?from=${from}&to=${to}&country=${country}&format=xml`), "_blank");

  const downloadPdf = () =>
    window.open(api.downloadUrl(`/api/accounting/vat-return/pdf?from=${from}&to=${to}&country=${country}`), "_blank");

  async function lockPeriod() {
    setLockLoading(true);
    try {
      await api.post("/api/accounting/vat-return/periods", { country, from_date: from, to_date: to });
      toast.success("Period locked and saved");
      await loadPeriods();
    } catch {
      toast.error("Failed to lock period");
    } finally {
      setLockLoading(false);
    }
  }

  async function filePeriod(id: string) {
    setFileSaving(true);
    try {
      await api.patch(`/api/accounting/vat-return/periods/${id}/file`, { reference: fileRef || null });
      toast.success("Marked as filed");
      setFileModalId(null);
      setFileRef("");
      await loadPeriods();
    } catch {
      toast.error("Failed to update status");
    } finally {
      setFileSaving(false);
    }
  }

  const info = COUNTRY_INFO[country];
  const alreadyLocked = periods.some((p) => p.from_date === from && p.to_date === to);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <ReceiptText className="w-6 h-6 text-indigo-400" />
        <div>
          <h1 className="text-xl font-bold vf-text-1">VAT Return</h1>
          <p className="text-xs vf-text-m mt-0.5">{info.flag} {info.name} · {info.freq}</p>
        </div>
      </div>

      {/* Selector panel */}
      <div className="vf-section p-5 space-y-4">
        {/* Country */}
        <div className="flex gap-2">
          {(["SE", "NO", "AE"] as Country[]).map((c) => (
            <button key={c} onClick={() => { setCountry(c); setResult(null); }}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                country === c
                  ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"
                  : "vf-section border border-white/10 vf-text-m hover:vf-text-1"
              }`}>
              <span>{COUNTRY_INFO[c].flag}</span><span>{c}</span>
            </button>
          ))}
        </div>

        {/* Quarter / custom */}
        <div>
          <div className="flex gap-2 flex-wrap mb-3">
            {QUARTERS.map((q) => (
              <button key={q.label} onClick={() => { setUseCustom(false); setSelectedQ(q.label); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  !useCustom && selectedQ === q.label
                    ? "bg-indigo-500/20 text-indigo-300"
                    : "vf-section vf-text-m hover:vf-text-1"
                }`}>
                {q.label} {year}
              </button>
            ))}
            <button onClick={() => setUseCustom(true)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                useCustom ? "bg-indigo-500/20 text-indigo-300" : "vf-section vf-text-m hover:vf-text-1"
              }`}>
              Custom
            </button>
          </div>
          <div className="flex items-end gap-3 flex-wrap">
            {!useCustom && (
              <div>
                <label className="text-xs vf-text-m block mb-1">Year</label>
                <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="vf-input text-sm">
                  {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            )}
            {useCustom && (
              <>
                <div>
                  <label className="text-xs vf-text-m block mb-1">From</label>
                  <input type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} className="vf-input text-sm" />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">To</label>
                  <input type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)} className="vf-input text-sm" />
                </div>
              </>
            )}
            <button onClick={run} disabled={loading} className="vf-btn text-sm px-5 py-2 flex items-center gap-1.5">
              {loading ? <><Loader2 className="w-3 h-3 animate-spin" /> Calculating…</> : "Generate"}
            </button>
          </div>
          {from && to && <p className="text-xs vf-text-m mt-2">Period: {from} — {to}</p>}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 rounded-lg px-4 py-3 bg-amber-500/10 border border-amber-500/20">
        <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-amber-300/80">
          Management estimate from Varuflow data. Expense input VAT uses assumed standard rate.
          Verify all figures with your accountant before submitting to the tax authority.
        </p>
      </div>

      {result && !loading && (
        <>
          {/* Net VAT banner */}
          <div className={`flex items-center justify-between rounded-xl px-5 py-4 ${
            Number(result.net_vat_payable) >= 0 ? "bg-amber-500/15 border border-amber-500/25" : "bg-emerald-500/15 border border-emerald-500/25"
          }`}>
            <div>
              <p className="text-xs vf-text-m">{result.from_date} – {result.to_date}</p>
              <p className="text-sm font-bold vf-text-1 mt-0.5">
                {Number(result.net_vat_payable) >= 0 ? "VAT payable to authority" : "VAT refund due"}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <span className={`text-2xl font-bold font-mono ${
                Number(result.net_vat_payable) >= 0 ? "text-amber-300" : "text-emerald-400"
              }`}>
                {fmt(Math.abs(Number(result.net_vat_payable)))}
              </span>
              {!alreadyLocked ? (
                <button onClick={lockPeriod} disabled={lockLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/20 text-xs vf-text-m hover:vf-text-1 transition-colors disabled:opacity-50">
                  <Lock className="w-3 h-3" />
                  {lockLoading ? "Saving…" : "Lock period"}
                </button>
              ) : (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <CheckCircle2 className="w-3 h-3" /> Saved
                </span>
              )}
            </div>
          </div>

          {/* Box breakdown */}
          <div className="vf-section overflow-hidden">
            <div className="px-5 py-3 border-b border-white/10">
              <p className="text-sm font-semibold vf-text-1">{info.name} — Box breakdown</p>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs vf-text-m border-b border-white/10">
                  <th className="text-left px-5 py-2 font-medium w-24">Box</th>
                  <th className="text-left px-5 py-2 font-medium">Description</th>
                  <th className="text-right px-5 py-2 font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {result.boxes.map((box) => {
                  const isNet = box.label.includes("49") || box.label.includes("3700") || box.label === "12";
                  const n = Number(box.amount);
                  return (
                    <tr key={box.label} className={`${isNet ? "border-t border-white/20 bg-white/5" : "hover:bg-white/3"} transition-colors`}>
                      <td className={`px-5 py-3 font-mono text-xs ${isNet ? "font-bold vf-text-1" : "vf-text-m"}`}>{box.label}</td>
                      <td className={`px-5 py-3 ${isNet ? "font-bold vf-text-1" : "vf-text-m"}`}>{box.description}</td>
                      <td className={`px-5 py-3 text-right font-mono tabular-nums ${
                        isNet
                          ? n > 0 ? "font-bold text-amber-300" : "font-bold text-emerald-400"
                          : "vf-text-1"
                      }`}>
                        {fmt(box.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Export actions */}
          <div className="flex gap-2">
            <button onClick={downloadXml} className="vf-btn text-xs px-4 py-2 flex items-center gap-1.5">
              <FileText className="w-4 h-4" /> Download XML
            </button>
            <button onClick={downloadPdf} className="vf-btn text-xs px-4 py-2 flex items-center gap-1.5">
              <Download className="w-4 h-4" /> Download PDF
            </button>
          </div>

          {/* Audit trail */}
          <AuditSection from={from} to={to} country={country} />
        </>
      )}

      {/* Filing history */}
      {periods.length > 0 && (
        <div className="vf-section overflow-hidden">
          <div className="px-5 py-3 border-b border-white/10">
            <p className="text-sm font-semibold vf-text-1">Filing history — {country}</p>
          </div>
          <div className="divide-y divide-white/5">
            {periods.map((p) => (
              <div key={p.id} className="flex items-center justify-between px-5 py-3 flex-wrap gap-2">
                <div>
                  <p className="text-sm vf-text-1">{p.from_date} — {p.to_date}</p>
                  {p.reference && <p className="text-xs vf-text-m">Ref: {p.reference}</p>}
                  {p.filed_at && <p className="text-xs vf-text-m">Filed {new Date(p.filed_at).toLocaleDateString("en-GB")}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded ${
                    p.status === "FILED" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-300"
                  }`}>
                    {p.status === "FILED"
                      ? <><CheckCircle2 className="w-3 h-3" /> Filed</>
                      : <><Clock className="w-3 h-3" /> Unfiled</>
                    }
                  </span>
                  <span className={`font-mono text-sm font-semibold ${
                    Number(p.net_vat_payable) > 0 ? "text-amber-300" : "text-emerald-400"
                  }`}>
                    {fmt(p.net_vat_payable)}
                  </span>
                  {p.status === "UNFILED" && (
                    <button
                      onClick={() => { setFileModalId(p.id); setFileRef(""); }}
                      className="text-xs px-2 py-1 rounded border border-white/15 vf-text-m hover:vf-text-1 transition-colors"
                    >
                      Mark filed
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* File confirmation modal */}
      {fileModalId && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="vf-section rounded-2xl w-full max-w-sm p-5 space-y-4">
            <p className="text-sm font-semibold vf-text-1">Mark period as filed</p>
            <div>
              <label className="text-xs vf-text-m block mb-1">Submission reference (optional)</label>
              <input autoFocus type="text" value={fileRef} onChange={(e) => setFileRef(e.target.value)}
                placeholder="e.g. SE-MOMS-2025-Q1-12345" className="vf-input text-sm w-full" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setFileModalId(null)} className="vf-btn-ghost text-xs px-4 py-2">Cancel</button>
              <button onClick={() => filePeriod(fileModalId!)} disabled={fileSaving}
                className="vf-btn text-xs px-4 py-2 disabled:opacity-50">
                {fileSaving ? "Saving…" : "Confirm filed"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
