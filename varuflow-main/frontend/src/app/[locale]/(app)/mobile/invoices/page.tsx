"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  FileText, Plus, Wifi, WifiOff, RefreshCw, Trash2,
  Search, CheckCircle2, Clock, AlertCircle, X,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

const MAX_OFFLINE = 20;

const CUSTOMERS_CACHE_KEY = "varuflow_cached_customers";
const PRODUCTS_CACHE_KEY = "varuflow_cached_products";
const OFFLINE_INVOICES_KEY = "varuflow_offline_invoices";

interface CachedCustomer { id: string; company_name: string; email?: string }
interface CachedProduct { id: string; name: string; sku?: string; price?: number; tax_rate?: number }

interface OfflineLineItem { product_id?: string; description: string; quantity: number; unit_price: number; tax_rate: number }
interface OfflineInvoice {
  client_sync_id: string;         // stable UUID for Idempotency-Key
  customer_id: string;
  customer_name: string;          // denormalised for display
  issue_date: string;
  due_date: string;
  notes: string;
  currency: string;
  line_items: OfflineLineItem[];
  created_at: string;             // local timestamp
  sync_status: "pending" | "synced" | "error";
  server_invoice_number?: string;
  error_message?: string;
}

function loadLocal<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; }
  catch { return fallback; }
}
function saveLocal(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value));
}

function calcTotals(items: OfflineLineItem[]) {
  const subtotal = items.reduce((s, l) => s + l.quantity * l.unit_price, 0);
  const vat = items.reduce((s, l) => s + l.quantity * l.unit_price * (l.tax_rate / 100), 0);
  return { subtotal, vat, total: subtotal + vat };
}

// ─── Line Item Row ────────────────────────────────────────────────────────────

function LineItemRow({
  item, idx, products,
  onChange, onRemove,
}: {
  item: OfflineLineItem; idx: number;
  products: CachedProduct[];
  onChange: (idx: number, field: keyof OfflineLineItem, value: string | number) => void;
  onRemove: (idx: number) => void;
}) {
  const [prodSearch, setProdSearch] = useState("");
  const matches = prodSearch
    ? products.filter(p =>
        p.name.toLowerCase().includes(prodSearch.toLowerCase()) ||
        (p.sku && p.sku.toLowerCase().includes(prodSearch.toLowerCase()))
      ).slice(0, 6)
    : [];

  function pick(p: CachedProduct) {
    onChange(idx, "product_id", p.id);
    onChange(idx, "description", p.name);
    onChange(idx, "unit_price", p.price ?? 0);
    onChange(idx, "tax_rate", p.tax_rate ?? 25);
    setProdSearch("");
  }

  return (
    <div className="grid grid-cols-12 gap-2 items-start">
      {/* Description / product search */}
      <div className="col-span-12 sm:col-span-5 relative">
        {!item.product_id ? (
          <>
            <input className="input w-full" placeholder="Search product or type description…"
              value={prodSearch || item.description}
              onChange={e => { setProdSearch(e.target.value); onChange(idx, "description", e.target.value); }} />
            {matches.length > 0 && (
              <div className="absolute top-full left-0 right-0 z-10 bg-white border border-gray-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                {matches.map(p => (
                  <button key={p.id} onClick={() => pick(p)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50">
                    <span className="font-medium">{p.name}</span>
                    {p.sku && <span className="text-gray-400 text-xs ml-1">({p.sku})</span>}
                    {p.price != null && <span className="float-right text-gray-500">{p.price}</span>}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="flex items-center gap-1">
            <input className="input flex-1 text-sm" value={item.description}
              onChange={e => onChange(idx, "description", e.target.value)} />
            <button onClick={() => { onChange(idx, "product_id", ""); onChange(idx, "description", ""); }}
              className="text-gray-400 hover:text-gray-600"><X className="h-3.5 w-3.5" /></button>
          </div>
        )}
      </div>
      <div className="col-span-3 sm:col-span-2">
        <input className="input w-full" type="number" min="0.01" step="0.01" placeholder="Qty"
          value={item.quantity} onChange={e => onChange(idx, "quantity", parseFloat(e.target.value) || 0)} />
      </div>
      <div className="col-span-4 sm:col-span-2">
        <input className="input w-full" type="number" min="0" step="0.01" placeholder="Price"
          value={item.unit_price} onChange={e => onChange(idx, "unit_price", parseFloat(e.target.value) || 0)} />
      </div>
      <div className="col-span-3 sm:col-span-2">
        <input className="input w-full" type="number" min="0" max="100" step="1" placeholder="VAT%"
          value={item.tax_rate} onChange={e => onChange(idx, "tax_rate", parseFloat(e.target.value) || 0)} />
      </div>
      <div className="col-span-2 sm:col-span-1 flex items-center justify-end">
        <button onClick={() => onRemove(idx)} className="text-red-400 hover:text-red-600 pt-1">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function OfflineInvoicesPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [isOnline, setIsOnline] = useState(true);
  const [invoices, setInvoices] = useState<OfflineInvoice[]>([]);
  const [customers, setCustomers] = useState<CachedCustomer[]>([]);
  const [products, setProducts] = useState<CachedProduct[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [cacheLoading, setCacheLoading] = useState(false);

  // Customer search
  const [custSearch, setCustSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<CachedCustomer | null>(null);

  // Form
  const [form, setForm] = useState({
    issue_date: new Date().toISOString().split("T")[0],
    due_date: (() => { const d = new Date(); d.setDate(d.getDate() + 30); return d.toISOString().split("T")[0]; })(),
    notes: "",
    currency: "SEK",
  });
  const [lines, setLines] = useState<OfflineLineItem[]>([
    { description: "", quantity: 1, unit_price: 0, tax_rate: 25 },
  ]);

  const fetch_ = useCallback((url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts }), [apiBase]);

  // Online/offline
  useEffect(() => {
    setIsOnline(navigator.onLine);
    const up = () => setIsOnline(true);
    const dn = () => setIsOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", dn);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", dn); };
  }, []);

  // Load from localStorage on mount
  useEffect(() => {
    setInvoices(loadLocal(OFFLINE_INVOICES_KEY, []));
    setCustomers(loadLocal(CUSTOMERS_CACHE_KEY, []));
    setProducts(loadLocal(PRODUCTS_CACHE_KEY, []));
  }, []);

  // Cache customers + products when online
  async function refreshCache() {
    if (!isOnline) { toast.error("Cannot refresh cache while offline"); return; }
    setCacheLoading(true);
    try {
      const [cRes, pRes] = await Promise.all([
        fetch_("/api/invoicing/customers?limit=500&is_active=true"),
        fetch_("/api/inventory/items?limit=1000"),
      ]);
      if (cRes.ok) {
        const data = await cRes.json();
        const cached: CachedCustomer[] = (data.customers || data).map((c: { id: string; company_name: string; email?: string }) => ({
          id: c.id, company_name: c.company_name, email: c.email,
        }));
        saveLocal(CUSTOMERS_CACHE_KEY, cached);
        setCustomers(cached);
        toast.success(`Cached ${cached.length} customers`);
      }
      if (pRes.ok) {
        const data = await pRes.json();
        const cached: CachedProduct[] = (data.items || data).map((p: { id: string; name: string; sku?: string; price?: number; tax_rate?: number }) => ({
          id: p.id, name: p.name, sku: p.sku,
          price: p.price, tax_rate: p.tax_rate,
        }));
        saveLocal(PRODUCTS_CACHE_KEY, cached);
        setProducts(cached);
      }
    } catch {
      toast.error("Failed to refresh cache");
    } finally {
      setCacheLoading(false);
    }
  }

  // Auto-refresh cache when coming online
  useEffect(() => {
    if (isOnline && customers.length === 0) {
      refreshCache();
    }
  }, [isOnline]);

  function updateInvoices(updated: OfflineInvoice[]) {
    setInvoices(updated);
    saveLocal(OFFLINE_INVOICES_KEY, updated);
  }

  // ── Create invoice ──

  function addLine() {
    setLines(l => [...l, { description: "", quantity: 1, unit_price: 0, tax_rate: 25 }]);
  }

  function removeLine(idx: number) {
    if (lines.length === 1) return;
    setLines(l => l.filter((_, i) => i !== idx));
  }

  function updateLine(idx: number, field: keyof OfflineLineItem, value: string | number) {
    setLines(l => l.map((ln, i) => i === idx ? { ...ln, [field]: value } : ln));
  }

  function saveOffline() {
    if (!selectedCustomer) { toast.error("Select a customer"); return; }
    const validLines = lines.filter(l => l.description.trim() && l.unit_price > 0);
    if (!validLines.length) { toast.error("Add at least one line item with a price"); return; }

    const current = loadLocal<OfflineInvoice[]>(OFFLINE_INVOICES_KEY, []);
    if (current.filter(i => i.sync_status === "pending").length >= MAX_OFFLINE) {
      toast.error(`Maximum ${MAX_OFFLINE} offline invoices reached — sync first`);
      return;
    }

    const inv: OfflineInvoice = {
      client_sync_id: crypto.randomUUID(),
      customer_id: selectedCustomer.id,
      customer_name: selectedCustomer.company_name,
      issue_date: form.issue_date,
      due_date: form.due_date,
      notes: form.notes,
      currency: form.currency,
      line_items: validLines,
      created_at: new Date().toISOString(),
      sync_status: "pending",
    };

    const updated = [inv, ...current];
    updateInvoices(updated);
    toast.success(isOnline ? "Saved — ready to sync" : "Saved offline");

    // Reset form
    setSelectedCustomer(null);
    setCustSearch("");
    setLines([{ description: "", quantity: 1, unit_price: 0, tax_rate: 25 }]);
    setForm(f => ({ ...f, notes: "" }));
    setShowCreate(false);

    // Auto-sync if online
    if (isOnline) syncInvoices(updated);
  }

  // ── Sync ──

  async function syncInvoices(queue?: OfflineInvoice[]) {
    const all = queue ?? loadLocal<OfflineInvoice[]>(OFFLINE_INVOICES_KEY, []);
    const pending = all.filter(i => i.sync_status === "pending");
    if (!pending.length) { toast.info("Nothing to sync"); return; }
    setSyncing(true);

    const updated = [...all];
    for (const inv of pending) {
      try {
        const body = {
          customer_id: inv.customer_id,
          issue_date: inv.issue_date,
          due_date: inv.due_date,
          notes: inv.notes || undefined,
          currency: inv.currency,
          line_items: inv.line_items.map(l => ({
            description: l.description,
            quantity: l.quantity,
            unit_price: l.unit_price,
            tax_rate: l.tax_rate,
            product_id: l.product_id || undefined,
          })),
        };
        const res = await fetch_("/api/invoicing/invoices", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": inv.client_sync_id,
          },
          body: JSON.stringify(body),
        });

        const idx = updated.findIndex(i => i.client_sync_id === inv.client_sync_id);
        if (res.ok) {
          const created = await res.json();
          updated[idx] = { ...updated[idx], sync_status: "synced", server_invoice_number: created.invoice_number };
          toast.success(`Synced invoice ${created.invoice_number}`);
        } else {
          const e = await res.json();
          updated[idx] = { ...updated[idx], sync_status: "error", error_message: e.detail || "Unknown error" };
        }
      } catch {
        const idx = updated.findIndex(i => i.client_sync_id === inv.client_sync_id);
        updated[idx] = { ...updated[idx], sync_status: "error", error_message: "Network error" };
      }
    }

    updateInvoices(updated);
    setSyncing(false);
  }

  function deleteInvoice(sync_id: string) {
    updateInvoices(loadLocal<OfflineInvoice[]>(OFFLINE_INVOICES_KEY, []).filter(i => i.client_sync_id !== sync_id));
    toast.success("Removed");
  }

  function retryInvoice(sync_id: string) {
    const all = loadLocal<OfflineInvoice[]>(OFFLINE_INVOICES_KEY, []);
    const updated = all.map(i => i.client_sync_id === sync_id ? { ...i, sync_status: "pending" as const, error_message: undefined } : i);
    updateInvoices(updated);
    syncInvoices(updated);
  }

  const pending = invoices.filter(i => i.sync_status === "pending").length;
  const custMatches = custSearch
    ? customers.filter(c => c.company_name.toLowerCase().includes(custSearch.toLowerCase())).slice(0, 8)
    : [];

  const { subtotal, vat, total } = calcTotals(lines);

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Offline Invoices</h1>
          <p className="mt-1 text-sm text-gray-500">Create invoices without internet — synced automatically when connected.</p>
        </div>
        <div className="flex items-center gap-2">
          {pending > 0 && (
            <button onClick={() => syncInvoices()} disabled={syncing || !isOnline}
              className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
              {syncing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
              Sync {pending}
            </button>
          )}
          <button onClick={() => setShowCreate(v => !v)} className="btn-primary flex items-center gap-2">
            <Plus className="h-4 w-4" /> New Invoice
          </button>
        </div>
      </div>

      {/* Status banner */}
      {!isOnline ? (
        <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <WifiOff className="h-4 w-4 flex-shrink-0" />
          Offline mode — invoices will be saved locally (max {MAX_OFFLINE}) and synced when connected.
        </div>
      ) : customers.length === 0 ? (
        <div className="flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          <span>Customer and product list not cached yet.</span>
          <button onClick={refreshCache} disabled={cacheLoading}
            className="flex items-center gap-1.5 font-medium underline disabled:opacity-50">
            {cacheLoading && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
            Cache now ({customers.length === 0 ? "0" : customers.length} customers)
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between rounded-xl border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700">
          <span>{customers.length} customers · {products.length} products cached</span>
          <button onClick={refreshCache} disabled={cacheLoading}
            className="flex items-center gap-1 hover:underline disabled:opacity-50">
            <RefreshCw className={`h-3 w-3 ${cacheLoading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="rounded-xl border border-blue-200 bg-white p-5 space-y-5">
          <h2 className="font-semibold text-gray-900">New Invoice</h2>

          {/* Customer */}
          <div className="relative">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Customer *</label>
            {selectedCustomer ? (
              <div className="flex items-center justify-between rounded-lg border border-gray-300 px-3 py-2">
                <span className="text-sm font-medium text-gray-900">{selectedCustomer.company_name}</span>
                <button onClick={() => setSelectedCustomer(null)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <input className="input w-full pl-8" placeholder="Search customer…" value={custSearch}
                    onChange={e => setCustSearch(e.target.value)} />
                </div>
                {custMatches.length > 0 && (
                  <div className="absolute left-0 right-0 z-10 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
                    {custMatches.map(c => (
                      <button key={c.id} onClick={() => { setSelectedCustomer(c); setCustSearch(""); }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50">
                        {c.company_name}
                      </button>
                    ))}
                  </div>
                )}
                {custSearch.length > 1 && custMatches.length === 0 && (
                  <p className="text-xs text-gray-400 mt-1">No matches — refresh cache or check spelling.</p>
                )}
              </>
            )}
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Issue date</label>
              <input className="input w-full" type="date" value={form.issue_date}
                onChange={e => setForm(f => ({ ...f, issue_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Due date</label>
              <input className="input w-full" type="date" value={form.due_date}
                onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))} />
            </div>
          </div>

          {/* Currency */}
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Currency</label>
            <select className="input w-32" value={form.currency}
              onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}>
              {["SEK", "EUR", "NOK", "DKK", "USD"].map(c => <option key={c}>{c}</option>)}
            </select>
          </div>

          {/* Line items */}
          <div className="space-y-2">
            <div className="hidden sm:grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 px-0">
              <div className="col-span-5">Description</div>
              <div className="col-span-2">Qty</div>
              <div className="col-span-2">Price</div>
              <div className="col-span-2">VAT%</div>
              <div className="col-span-1" />
            </div>
            {lines.map((line, i) => (
              <LineItemRow key={i} item={line} idx={i} products={products}
                onChange={updateLine} onRemove={removeLine} />
            ))}
            <button onClick={addLine} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
              <Plus className="h-3 w-3" /> Add line
            </button>
          </div>

          {/* Totals */}
          <div className="rounded-lg bg-gray-50 p-3 space-y-1 text-sm">
            <div className="flex justify-between text-gray-600"><span>Subtotal</span><span>{subtotal.toFixed(2)} {form.currency}</span></div>
            <div className="flex justify-between text-gray-600"><span>VAT</span><span>{vat.toFixed(2)} {form.currency}</span></div>
            <div className="flex justify-between font-semibold text-gray-900 pt-1 border-t border-gray-200">
              <span>Total</span><span>{total.toFixed(2)} {form.currency}</span>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Notes (optional)</label>
            <textarea className="input w-full" rows={2} value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={() => setShowCreate(false)} className="btn-secondary">Cancel</button>
            <button onClick={saveOffline} className="btn-primary flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              {isOnline ? "Save & Sync" : "Save Offline"}
            </button>
          </div>
        </div>
      )}

      {/* Invoice queue */}
      <div className="space-y-2">
        <p className="text-sm font-semibold text-gray-700">Queue ({invoices.length} / {MAX_OFFLINE})</p>
        {invoices.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-10">No offline invoices. Create one above.</p>
        )}
        {invoices.map(inv => (
          <div key={inv.client_sync_id} className={`rounded-xl border bg-white p-4 ${
            inv.sync_status === "synced" ? "border-green-200" :
            inv.sync_status === "error" ? "border-red-200" : "border-amber-200"
          }`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {inv.sync_status === "synced"
                  ? <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                  : inv.sync_status === "error"
                  ? <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                  : <Clock className="h-4 w-4 text-amber-500 flex-shrink-0" />}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{inv.customer_name}</p>
                  <p className="text-xs text-gray-500">
                    {inv.issue_date} · {inv.currency} {calcTotals(inv.line_items).total.toFixed(2)}
                    {inv.sync_status === "synced" && inv.server_invoice_number && ` · ${inv.server_invoice_number}`}
                  </p>
                  {inv.sync_status === "pending" && (
                    <span className="text-xs text-amber-600 font-medium">Pending sync</span>
                  )}
                  {inv.sync_status === "error" && (
                    <span className="text-xs text-red-500">{inv.error_message}</span>
                  )}
                </div>
              </div>
              <div className="flex gap-1.5 flex-shrink-0">
                {inv.sync_status === "error" && (
                  <button onClick={() => retryInvoice(inv.client_sync_id)}
                    className="flex items-center gap-1 rounded-lg border border-blue-200 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50">
                    <RefreshCw className="h-3 w-3" /> Retry
                  </button>
                )}
                {inv.sync_status === "synced" && (
                  <button onClick={() => deleteInvoice(inv.client_sync_id)}
                    className="text-gray-300 hover:text-gray-500">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
                {inv.sync_status === "pending" && !syncing && (
                  <button onClick={() => deleteInvoice(inv.client_sync_id)}
                    className="text-gray-300 hover:text-red-400">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
