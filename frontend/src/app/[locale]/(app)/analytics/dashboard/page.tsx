"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Plus, Trash2, GripVertical, Settings2, BarChart3, Users, Package, FileText, TrendingDown, DollarSign, AlertTriangle, CreditCard } from "lucide-react";

interface Widget {
  id: string; widget_type: string;
  position: { x: number; y: number; w: number; h: number };
  config: Record<string, unknown>;
}
interface Dashboard { id: string; name: string; is_default: boolean; widget_count: number; updated_at: string }
interface WidgetData { data?: unknown[]; count?: number; total?: number; amount?: number }

const WIDGET_CATALOG = [
  { type: "revenue_trend",    label: "Revenue Trend",     icon: BarChart3,    desc: "Monthly revenue over time" },
  { type: "top_customers",    label: "Top Customers",      icon: Users,        desc: "Customers by revenue" },
  { type: "top_products",     label: "Top Products",       icon: Package,      desc: "Products by revenue" },
  { type: "invoice_status",   label: "Invoice Status",     icon: FileText,     desc: "Status breakdown" },
  { type: "expense_summary",  label: "Expense Summary",    icon: CreditCard,   desc: "Expenses by category" },
  { type: "outstanding_ar",   label: "Outstanding AR",     icon: DollarSign,   desc: "Unpaid invoices total" },
  { type: "overdue_count",    label: "Overdue Alert",      icon: AlertTriangle,desc: "Overdue invoices count" },
];

const WIDGET_ICON: Record<string, React.ComponentType<{className?: string}>> = {
  revenue_trend: BarChart3, top_customers: Users, top_products: Package,
  invoice_status: FileText, expense_summary: CreditCard, outstanding_ar: DollarSign,
  overdue_count: AlertTriangle,
};

export default function DashboardBuilderPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [activeDash, setActiveDash] = useState<string | null>(null);
  const [layout, setLayout] = useState<Widget[]>([]);
  const [widgetData, setWidgetData] = useState<Record<string, WidgetData>>({});
  const [showCatalog, setShowCatalog] = useState(false);
  const [showNewDash, setShowNewDash] = useState(false);
  const [newDashName, setNewDashName] = useState("");
  const [saving, setSaving] = useState(false);
  const [months, setMonths] = useState(6);

  const f = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function loadDashboards() {
    const res = await f("/api/bi/dashboards");
    if (res.ok) {
      const d = await res.json();
      setDashboards(d.dashboards);
      if (d.dashboards.length && !activeDash) {
        setActiveDash(d.dashboards[0].id);
      }
    }
  }

  async function loadDashboard(id: string) {
    const res = await f(`/api/bi/dashboards/${id}`);
    if (res.ok) {
      const d = await res.json();
      setLayout(d.layout || []);
    }
  }

  const loadWidgetData = useCallback(async (widgets: Widget[]) => {
    const results: Record<string, WidgetData> = {};
    await Promise.all(
      widgets.map(async (w) => {
        const res = await f(`/api/bi/widgets/${w.widget_type}?months=${months}`);
        if (res.ok) results[w.id] = await res.json();
      })
    );
    setWidgetData(results);
  }, [months, apiBase]);

  useEffect(() => { loadDashboards(); }, []);
  useEffect(() => { if (activeDash) loadDashboard(activeDash); }, [activeDash]);
  useEffect(() => { if (layout.length) loadWidgetData(layout); }, [layout, loadWidgetData]);

  async function createDashboard() {
    if (!newDashName.trim()) { toast.error("Enter a name"); return; }
    const res = await f("/api/bi/dashboards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newDashName, layout: [] }),
    });
    if (res.ok) {
      const d = await res.json();
      toast.success("Dashboard created");
      setShowNewDash(false);
      setNewDashName("");
      await loadDashboards();
      setActiveDash(d.id);
    }
  }

  async function saveLayout() {
    if (!activeDash) return;
    setSaving(true);
    const res = await f(`/api/bi/dashboards/${activeDash}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout }),
    });
    if (res.ok) toast.success("Layout saved");
    else toast.error("Save failed");
    setSaving(false);
  }

  async function deleteDashboard(id: string) {
    await f(`/api/bi/dashboards/${id}`, { method: "DELETE" });
    setDashboards(d => d.filter(x => x.id !== id));
    if (activeDash === id) setActiveDash(null);
    toast.success("Deleted");
  }

  function addWidget(type: string) {
    const newW: Widget = {
      id: crypto.randomUUID(),
      widget_type: type,
      position: { x: 0, y: layout.length, w: 1, h: 1 },
      config: {},
    };
    setLayout(l => [...l, newW]);
    setShowCatalog(false);
  }

  function removeWidget(id: string) {
    setLayout(l => l.filter(w => w.id !== id));
  }

  function renderWidgetContent(w: Widget) {
    const d = widgetData[w.id];
    if (!d) return <div className="animate-pulse h-20 bg-gray-100 rounded-lg" />;

    if (w.widget_type === "revenue_trend" && Array.isArray(d.data)) {
      const max = Math.max(...(d.data as {revenue: number}[]).map(x => x.revenue), 1);
      return (
        <div className="flex items-end gap-1 h-20">
          {(d.data as {month: string; revenue: number}[]).map(item => (
            <div key={item.month} className="flex-1 flex flex-col items-center gap-1">
              <div className="w-full bg-blue-500 rounded-sm" style={{ height: `${(item.revenue / max) * 64}px` }} />
              <span className="text-[9px] text-gray-400">{item.month.slice(5)}</span>
            </div>
          ))}
        </div>
      );
    }

    if ((w.widget_type === "top_customers" || w.widget_type === "top_products") && Array.isArray(d.data)) {
      return (
        <div className="space-y-1">
          {(d.data as {name: string; revenue: number}[]).slice(0, 5).map((item, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-gray-700 truncate max-w-[120px]">{item.name}</span>
              <span className="font-medium text-gray-900">{Number(item.revenue).toLocaleString("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 })}</span>
            </div>
          ))}
        </div>
      );
    }

    if (w.widget_type === "invoice_status" && Array.isArray(d.data)) {
      return (
        <div className="space-y-1">
          {(d.data as {status: string; count: number; total: number}[]).map(item => (
            <div key={item.status} className="flex items-center justify-between text-xs">
              <span className="capitalize text-gray-700">{item.status}</span>
              <span className="font-medium">{item.count}</span>
            </div>
          ))}
        </div>
      );
    }

    if ((w.widget_type === "outstanding_ar" || w.widget_type === "overdue_count")) {
      const amount = d.total ?? d.amount ?? 0;
      const count = d.count ?? 0;
      return (
        <div className="text-center py-2">
          <p className="text-3xl font-bold text-red-600">{count}</p>
          <p className="text-sm text-gray-500 mt-1">{Number(amount).toLocaleString("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 })}</p>
        </div>
      );
    }

    if (w.widget_type === "expense_summary" && Array.isArray(d.data)) {
      return (
        <div className="space-y-1">
          {(d.data as {category: string; total: number}[]).slice(0, 5).map((item, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-gray-700 truncate max-w-[120px]">{item.category}</span>
              <span className="font-medium">{Number(item.total).toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</span>
            </div>
          ))}
        </div>
      );
    }

    return <div className="text-xs text-gray-400">No data</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Custom Dashboards</h1>
          <p className="mt-1 text-sm text-gray-500">Build and arrange KPI widgets for your home screen.</p>
        </div>
        <div className="flex gap-2">
          <select className="input text-sm" value={months} onChange={e => setMonths(Number(e.target.value))}>
            {[1, 3, 6, 12, 24].map(m => <option key={m} value={m}>{m}m</option>)}
          </select>
          {activeDash && (
            <>
              <button onClick={() => setShowCatalog(true)} className="btn-secondary flex items-center gap-1.5">
                <Plus className="h-3.5 w-3.5" /> Add Widget
              </button>
              <button onClick={saveLayout} disabled={saving} className="btn-primary">
                {saving ? "Saving…" : "Save Layout"}
              </button>
            </>
          )}
          <button onClick={() => setShowNewDash(true)} className="btn-secondary flex items-center gap-1.5">
            <Plus className="h-3.5 w-3.5" /> New Dashboard
          </button>
        </div>
      </div>

      {/* New dashboard modal */}
      {showNewDash && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 flex gap-3 items-center">
          <input className="input flex-1" placeholder="Dashboard name" value={newDashName} onChange={e => setNewDashName(e.target.value)} autoFocus />
          <button onClick={createDashboard} className="btn-primary">Create</button>
          <button onClick={() => setShowNewDash(false)} className="btn-secondary">Cancel</button>
        </div>
      )}

      {/* Widget catalog */}
      {showCatalog && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-sm font-semibold text-gray-700 mb-3">Choose a widget to add</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {WIDGET_CATALOG.map(w => (
              <button key={w.type} onClick={() => addWidget(w.type)}
                className="flex flex-col items-start gap-1.5 p-3 rounded-xl border border-gray-200 hover:border-blue-400 hover:bg-blue-50 text-left transition-all">
                <w.icon className="h-4 w-4 text-blue-500" />
                <span className="text-xs font-medium text-gray-900">{w.label}</span>
                <span className="text-[10px] text-gray-400">{w.desc}</span>
              </button>
            ))}
          </div>
          <button onClick={() => setShowCatalog(false)} className="mt-3 btn-secondary text-xs">Cancel</button>
        </div>
      )}

      <div className="flex gap-6">
        {/* Sidebar: dashboard list */}
        <div className="w-48 shrink-0 space-y-1">
          {dashboards.map(d => (
            <div key={d.id} className={`flex items-center gap-2 rounded-xl px-3 py-2 cursor-pointer transition-all group ${
              activeDash === d.id ? "bg-blue-50 border border-blue-200" : "hover:bg-gray-50"
            }`} onClick={() => setActiveDash(d.id)}>
              <span className="flex-1 text-sm text-gray-900 truncate">{d.name}</span>
              <button onClick={(e) => { e.stopPropagation(); deleteDashboard(d.id); }}
                className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500">
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
          {dashboards.length === 0 && (
            <p className="text-xs text-gray-400 px-3">No dashboards yet.</p>
          )}
        </div>

        {/* Widget grid */}
        <div className="flex-1">
          {!activeDash ? (
            <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
              Create or select a dashboard to start building.
            </div>
          ) : layout.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
              No widgets yet. Click <strong>Add Widget</strong> to get started.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {layout.map(w => {
                const Icon = WIDGET_ICON[w.widget_type] || Settings2;
                const label = WIDGET_CATALOG.find(x => x.type === w.widget_type)?.label || w.widget_type;
                return (
                  <div key={w.id} className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <GripVertical className="h-4 w-4 text-gray-300 cursor-grab" />
                        <Icon className="h-4 w-4 text-blue-500" />
                        <span className="text-sm font-medium text-gray-900">{label}</span>
                      </div>
                      <button onClick={() => removeWidget(w.id)} className="text-gray-300 hover:text-red-500">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {renderWidgetContent(w)}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
