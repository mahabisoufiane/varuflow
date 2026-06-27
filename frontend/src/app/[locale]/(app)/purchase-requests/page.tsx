"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Plus, AlertCircle, FileText, BarChart2, CheckCircle, XCircle, Clock } from "lucide-react";

interface PurchaseRequestItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  product_id: string | null;
}

interface PurchaseRequest {
  id: string;
  title: string;
  justification: string | null;
  requested_by: string;
  supplier_id: string | null;
  estimated_total: number;
  currency: string;
  status: string;
  urgency: string;
  budget_category: string | null;
  budget_exceeded: boolean;
  is_template: boolean;
  template_name: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  purchase_order_id: string | null;
  items: PurchaseRequestItem[];
  created_at: string | null;
}

interface Report {
  total_submitted: number;
  total_approved: number;
  total_rejected: number;
  total_pending: number;
  value_approved: number;
  value_pending: number;
  by_category: Record<string, { count: number; value: number }>;
}

interface ItemFormRow {
  description: string;
  quantity: string;
  unit_price: string;
}

const URGENCY_OPTS = ["low", "normal", "high", "urgent"];
const CATEGORIES = ["Office supplies", "IT equipment", "Software", "Facilities", "Travel", "Marketing", "Other"];

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

const URGENCY_BADGE: Record<string, string> = {
  low: "bg-gray-100 text-gray-600",
  normal: "bg-blue-50 text-blue-600",
  high: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

export default function PurchaseRequestsPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"requests" | "templates" | "report">("requests");
  const [statusFilter, setStatusFilter] = useState("");
  const [items, setItems] = useState<PurchaseRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [role, setRole] = useState<string>("MEMBER");

  const [report, setReport] = useState<Report | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  // Create form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: "",
    justification: "",
    estimated_total: "",
    currency: "SEK",
    urgency: "normal",
    budget_category: "",
    supplier_id: "",
    is_template: false,
    template_name: "",
  });
  const [lineItems, setLineItems] = useState<ItemFormRow[]>([{ description: "", quantity: "1", unit_price: "" }]);
  const [saving, setSaving] = useState(false);

  // Detail / review panel
  const [selected, setSelected] = useState<PurchaseRequest | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [reviewing, setReviewing] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      const data = await api.get(`/api/purchase-requests?${params}`);
      const all: PurchaseRequest[] = Array.isArray(data) ? data : [];
      setItems(all);
    } catch (e: any) {
      if (e?.status === 401) { router.push("/auth/login"); return; }
      setError("Failed to load purchase requests");
    } finally {
      setLoading(false);
    }
  }

  async function loadReport() {
    setReportLoading(true);
    try {
      const data = await api.get("/api/purchase-requests/report");
      setReport(data);
    } catch { setReport(null); }
    finally { setReportLoading(false); }
  }

  useEffect(() => {
    if (tab === "report") loadReport();
    else load();
  }, [tab, statusFilter]);

  function calcTotal() {
    const fromLines = lineItems.reduce((s, r) => {
      const q = parseFloat(r.quantity) || 0;
      const p = parseFloat(r.unit_price) || 0;
      return s + q * p;
    }, 0);
    return fromLines > 0 ? fromLines.toString() : form.estimated_total;
  }

  async function create() {
    if (!form.title.trim()) { alert("Title is required"); return; }
    setSaving(true);
    try {
      const filledItems = lineItems.filter(l => l.description.trim() && l.unit_price);
      const estimated = parseFloat(calcTotal()) || parseFloat(form.estimated_total) || 0;
      const body: Record<string, unknown> = {
        title: form.title,
        justification: form.justification || null,
        estimated_total: estimated,
        currency: form.currency,
        urgency: form.urgency,
        budget_category: form.budget_category || null,
        is_template: form.is_template,
        template_name: form.is_template ? (form.template_name || null) : null,
        items: filledItems.map(l => ({
          description: l.description,
          quantity: parseInt(l.quantity) || 1,
          unit_price: parseFloat(l.unit_price) || 0,
        })),
      };
      if (form.supplier_id) body.supplier_id = form.supplier_id;
      const data = await api.post("/api/purchase-requests", body);
      setItems(prev => [data, ...prev]);
      setShowForm(false);
      setForm({ title: "", justification: "", estimated_total: "", currency: "SEK", urgency: "normal", budget_category: "", supplier_id: "", is_template: false, template_name: "" });
      setLineItems([{ description: "", quantity: "1", unit_price: "" }]);
    } catch (e: any) {
      alert(e?.data?.detail ?? "Failed to submit request");
    } finally {
      setSaving(false);
    }
  }

  async function review(id: string, action: "approve" | "reject") {
    setReviewing(true);
    try {
      const data = await api.post(`/api/purchase-requests/${id}/${action}`, { note: reviewNote || null });
      setItems(prev => prev.map(r => r.id === id ? data : r));
      if (selected?.id === id) setSelected(data);
      setReviewNote("");
    } catch (e: any) {
      alert(e?.data?.detail ?? "Action failed");
    } finally {
      setReviewing(false);
    }
  }

  const displayed = items.filter(r => tab === "templates" ? r.is_template : !r.is_template);
  const isManager = role === "OWNER" || role === "ADMIN";

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Purchase Requests</h1>
          <p className="text-sm text-gray-500 mt-0.5">Submit and approve internal purchase requests</p>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="btn-primary flex items-center gap-1 text-sm">
          <Plus className="w-4 h-4" /> New Request
        </button>
      </div>

      {error && (
        <div className="rounded bg-red-50 border border-red-200 text-red-700 text-sm p-3 flex gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />{error}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {(["requests", "templates", "report"] as const).map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setSelected(null); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t ? "border-indigo-600 text-indigo-700" : "border-transparent text-gray-500 hover:text-gray-700"}`}
          >
            {t === "requests" ? "Requests" : t === "templates" ? "Templates" : "Spending Report"}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-xl border bg-white shadow-sm p-5 space-y-4">
          <h2 className="font-semibold text-gray-800">{form.is_template ? "New Request Template" : "New Purchase Request"}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Title *</label>
              <input className="input w-full" placeholder="e.g. Laptop for new hire" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Justification</label>
              <textarea className="input w-full" rows={2} placeholder="Why is this purchase needed?" value={form.justification} onChange={e => setForm(f => ({ ...f, justification: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Urgency</label>
              <select className="input w-full" value={form.urgency} onChange={e => setForm(f => ({ ...f, urgency: e.target.value }))}>
                {URGENCY_OPTS.map(u => <option key={u} value={u}>{u.charAt(0).toUpperCase() + u.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Budget category</label>
              <select className="input w-full" value={form.budget_category} onChange={e => setForm(f => ({ ...f, budget_category: e.target.value }))}>
                <option value="">— Select —</option>
                {CATEGORIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Currency</label>
              <select className="input w-full" value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}>
                {["SEK", "NOK", "DKK", "EUR", "USD"].map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Manual estimated total (if no line items)</label>
              <input type="number" className="input w-full" placeholder="0.00" value={form.estimated_total} onChange={e => setForm(f => ({ ...f, estimated_total: e.target.value }))} />
            </div>
          </div>

          {/* Line items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-500 font-medium">Line items</label>
              <button
                onClick={() => setLineItems(prev => [...prev, { description: "", quantity: "1", unit_price: "" }])}
                className="text-xs text-indigo-600 hover:underline"
              >
                + Add line
              </button>
            </div>
            <div className="space-y-2">
              {lineItems.map((row, i) => (
                <div key={i} className="grid grid-cols-[1fr_80px_100px_32px] gap-2 items-center">
                  <input
                    className="input text-sm"
                    placeholder="Description"
                    value={row.description}
                    onChange={e => setLineItems(prev => prev.map((r, j) => j === i ? { ...r, description: e.target.value } : r))}
                  />
                  <input
                    type="number"
                    className="input text-sm"
                    placeholder="Qty"
                    value={row.quantity}
                    onChange={e => setLineItems(prev => prev.map((r, j) => j === i ? { ...r, quantity: e.target.value } : r))}
                  />
                  <input
                    type="number"
                    className="input text-sm"
                    placeholder="Unit price"
                    value={row.unit_price}
                    onChange={e => setLineItems(prev => prev.map((r, j) => j === i ? { ...r, unit_price: e.target.value } : r))}
                  />
                  <button
                    onClick={() => setLineItems(prev => prev.filter((_, j) => j !== i))}
                    className="text-gray-300 hover:text-red-400 text-lg leading-none"
                    disabled={lineItems.length === 1}
                  >×</button>
                </div>
              ))}
            </div>
            {lineItems.some(l => l.unit_price) && (
              <p className="text-xs text-gray-500 mt-1">
                Calculated total: <strong>{parseFloat(calcTotal()).toLocaleString()} {form.currency}</strong>
              </p>
            )}
          </div>

          {/* Template toggle */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={form.is_template} onChange={e => setForm(f => ({ ...f, is_template: e.target.checked }))} />
              Save as template
            </label>
            {form.is_template && (
              <input
                className="input text-sm flex-1"
                placeholder="Template name"
                value={form.template_name}
                onChange={e => setForm(f => ({ ...f, template_name: e.target.value }))}
              />
            )}
          </div>

          <div className="flex gap-3">
            <button onClick={create} disabled={saving} className="btn-primary text-sm">
              {saving ? "Submitting…" : form.is_template ? "Save template" : "Submit request"}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Spending Report */}
      {tab === "report" && (
        <div className="space-y-5">
          {reportLoading && <div className="text-center text-gray-400 py-12">Loading report…</div>}
          {!reportLoading && report && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { label: "Total submitted", value: report.total_submitted, icon: FileText, color: "text-gray-700" },
                  { label: "Approved", value: report.total_approved, icon: CheckCircle, color: "text-green-600" },
                  { label: "Rejected", value: report.total_rejected, icon: XCircle, color: "text-red-500" },
                  { label: "Pending", value: report.total_pending, icon: Clock, color: "text-yellow-600" },
                ].map(card => (
                  <div key={card.label} className="rounded-xl border bg-white p-4 flex items-start gap-3 shadow-sm">
                    <card.icon className={`w-5 h-5 mt-0.5 shrink-0 ${card.color}`} />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{card.value}</p>
                      <p className="text-xs text-gray-500">{card.label}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border bg-white p-4 shadow-sm">
                  <p className="text-xs text-gray-500 mb-1">Approved value</p>
                  <p className="text-xl font-bold text-green-700">{report.value_approved.toLocaleString()} SEK</p>
                </div>
                <div className="rounded-xl border bg-white p-4 shadow-sm">
                  <p className="text-xs text-gray-500 mb-1">Pending value</p>
                  <p className="text-xl font-bold text-yellow-700">{report.value_pending.toLocaleString()} SEK</p>
                </div>
              </div>
              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2"><BarChart2 className="w-4 h-4" /> By category</h3>
                <div className="space-y-2">
                  {Object.entries(report.by_category).map(([cat, d]) => (
                    <div key={cat} className="flex items-center justify-between text-sm">
                      <span className="text-gray-700">{cat}</span>
                      <div className="flex gap-4 text-gray-500 text-xs">
                        <span>{d.count} request{d.count !== 1 ? "s" : ""}</span>
                        <span className="font-semibold text-gray-700">{d.value.toLocaleString()} SEK</span>
                      </div>
                    </div>
                  ))}
                  {Object.keys(report.by_category).length === 0 && (
                    <p className="text-gray-400 text-sm">No data yet.</p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Requests / Templates list */}
      {tab !== "report" && (
        <div className="flex gap-6">
          {/* List */}
          <div className="flex-1 min-w-0 space-y-3">
            {/* Status filter */}
            {tab === "requests" && (
              <div className="flex gap-1 flex-wrap">
                {["", "pending", "approved", "rejected"].map(s => (
                  <button
                    key={s || "all"}
                    onClick={() => setStatusFilter(s)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${statusFilter === s ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"}`}
                  >
                    {s ? s.charAt(0).toUpperCase() + s.slice(1) : "All"}
                  </button>
                ))}
              </div>
            )}

            {loading && <div className="text-center text-gray-400 py-12">Loading…</div>}

            {!loading && displayed.length === 0 && (
              <div className="text-center py-16 text-gray-400">
                {tab === "templates" ? "No templates saved yet." : "No purchase requests found."}
              </div>
            )}

            {displayed.map(req => (
              <div
                key={req.id}
                onClick={() => { setSelected(req); setReviewNote(""); }}
                className={`rounded-xl border bg-white shadow-sm p-4 cursor-pointer hover:shadow-md transition-shadow ${selected?.id === req.id ? "ring-2 ring-indigo-400" : ""}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900 truncate">{req.title}</span>
                      {!req.is_template && (
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[req.status] ?? "bg-gray-100 text-gray-700"}`}>
                          {req.status}
                        </span>
                      )}
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${URGENCY_BADGE[req.urgency] ?? "bg-gray-100 text-gray-600"}`}>
                        {req.urgency}
                      </span>
                      {req.budget_exceeded && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">Budget exceeded</span>
                      )}
                      {req.budget_category && (
                        <span className="text-xs text-gray-400">{req.budget_category}</span>
                      )}
                    </div>
                    {req.justification && (
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{req.justification}</p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      {req.created_at ? new Date(req.created_at).toLocaleDateString() : ""}
                      {req.items.length > 0 ? ` · ${req.items.length} line item${req.items.length !== 1 ? "s" : ""}` : ""}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-semibold text-gray-900">{req.estimated_total.toLocaleString()} {req.currency}</p>
                    {req.purchase_order_id && (
                      <p className="text-xs text-indigo-600 mt-0.5">PO created</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="w-80 shrink-0 rounded-xl border bg-white shadow-sm p-5 space-y-4 self-start sticky top-20">
              <div className="flex items-start justify-between">
                <h2 className="font-semibold text-gray-900 leading-tight">{selected.title}</h2>
                <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
              </div>

              {selected.justification && (
                <p className="text-sm text-gray-600">{selected.justification}</p>
              )}

              <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                <div><span className="font-medium text-gray-700">Status:</span> {selected.status}</div>
                <div><span className="font-medium text-gray-700">Urgency:</span> {selected.urgency}</div>
                <div><span className="font-medium text-gray-700">Category:</span> {selected.budget_category ?? "—"}</div>
                <div><span className="font-medium text-gray-700">Currency:</span> {selected.currency}</div>
                <div className="col-span-2"><span className="font-medium text-gray-700">Total:</span> {selected.estimated_total.toLocaleString()} {selected.currency}</div>
                {selected.review_note && (
                  <div className="col-span-2"><span className="font-medium text-gray-700">Review note:</span> {selected.review_note}</div>
                )}
                {selected.purchase_order_id && (
                  <div className="col-span-2 text-indigo-600">PO: {selected.purchase_order_id.slice(0, 8)}…</div>
                )}
              </div>

              {/* Line items */}
              {selected.items.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500">Line items</p>
                  <div className="text-xs divide-y border rounded overflow-hidden">
                    {selected.items.map(item => (
                      <div key={item.id} className="flex justify-between px-3 py-1.5">
                        <span className="text-gray-700">{item.description} × {item.quantity}</span>
                        <span className="text-gray-500">{(item.quantity * item.unit_price).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Approve / reject (managers only, pending only) */}
              {selected.status === "pending" && (
                <div className="space-y-2 pt-2 border-t">
                  <textarea
                    className="input w-full text-sm"
                    rows={2}
                    placeholder="Review note (optional)"
                    value={reviewNote}
                    onChange={e => setReviewNote(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => review(selected.id, "approve")}
                      disabled={reviewing}
                      className="flex-1 py-1.5 text-sm rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      {reviewing ? "…" : "Approve"}
                    </button>
                    <button
                      onClick={() => review(selected.id, "reject")}
                      disabled={reviewing}
                      className="flex-1 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {reviewing ? "…" : "Reject"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
