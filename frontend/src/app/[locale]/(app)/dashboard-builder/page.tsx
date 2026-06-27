"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  LayoutDashboard, Plus, Save, Trash2, RefreshCw, Share2, Star,
  BarChart3, FileText, Package, Users, TrendingUp, DollarSign,
  ChevronDown, ChevronUp, GripVertical, X, Eye
} from "lucide-react";

type DateRange = "today" | "this_week" | "this_month" | "this_quarter" | "this_year";
type WidgetSize = "1x1" | "2x1" | "2x2";

interface Widget {
  id: string;
  type: string;
  label: string;
  size: WidgetSize;
  data?: any;
  loading?: boolean;
}

interface Layout {
  id: string;
  name: string;
  widgets: Widget[];
  date_range: DateRange;
  is_default: boolean;
  shared_role?: string;
}

const WIDGET_LIBRARY = [
  { type: "revenue",         label: "Revenue",          icon: DollarSign,  description: "Total revenue for period" },
  { type: "invoice_summary", label: "Invoices",         icon: FileText,    description: "Invoice count & status breakdown" },
  { type: "stock_level",     label: "Stock Alerts",     icon: Package,     description: "Low stock & out-of-stock counts" },
  { type: "customer_count",  label: "Customers",        icon: Users,       description: "Total active customers" },
  { type: "pipeline_value",  label: "Open Receivables", icon: TrendingUp,  description: "Outstanding invoice value" },
];

const DATE_RANGES: { value: DateRange; label: string }[] = [
  { value: "today",        label: "Today" },
  { value: "this_week",    label: "This Week" },
  { value: "this_month",   label: "This Month" },
  { value: "this_quarter", label: "This Quarter" },
  { value: "this_year",    label: "This Year" },
];

const SIZE_OPTIONS: { value: WidgetSize; label: string }[] = [
  { value: "1x1", label: "Small" },
  { value: "2x1", label: "Wide" },
  { value: "2x2", label: "Large" },
];

function widgetColSpan(size: WidgetSize) {
  if (size === "2x1" || size === "2x2") return "col-span-2";
  return "col-span-1";
}

function widgetRowSpan(size: WidgetSize) {
  if (size === "2x2") return "row-span-2";
  return "row-span-1";
}

function WidgetCard({ widget, onRemove, onResize }: {
  widget: Widget;
  onRemove: () => void;
  onResize: (size: WidgetSize) => void;
}) {
  const [showSizes, setShowSizes] = useState(false);

  const renderData = () => {
    if (widget.loading) return <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />;
    const d = widget.data;
    if (!d) return <p className="text-muted-foreground text-sm">No data</p>;

    if (widget.type === "revenue" || widget.type === "customer_count" || widget.type === "pipeline_value") {
      return (
        <p className="text-3xl font-bold">
          {typeof d.value === "number" ? d.value.toLocaleString("sv-SE", { maximumFractionDigits: 0 }) : "—"}
        </p>
      );
    }
    if (widget.type === "invoice_summary") {
      return (
        <div className="space-y-1">
          {(d.items ?? []).slice(0, 4).map((item: any) => (
            <div key={item.status} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground capitalize">{item.status}</span>
              <span className="font-medium">{item.count}</span>
            </div>
          ))}
        </div>
      );
    }
    if (widget.type === "stock_level") {
      return (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-amber-600">Low stock</span>
            <span className="font-bold">{d.low_stock}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-red-600">Out of stock</span>
            <span className="font-bold">{d.out_of_stock}</span>
          </div>
        </div>
      );
    }
    return <pre className="text-xs text-muted-foreground">{JSON.stringify(d, null, 2)}</pre>;
  };

  return (
    <div className={`rounded-xl border bg-card p-4 group relative flex flex-col gap-3 min-h-[120px]
      ${widgetColSpan(widget.size)} ${widgetRowSpan(widget.size)}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
          <span className="text-sm font-semibold">{widget.label}</span>
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="relative">
            <button
              className="p-1 rounded hover:bg-muted text-xs text-muted-foreground"
              onClick={() => setShowSizes(s => !s)}
              title="Resize"
            >
              {widget.size}
            </button>
            {showSizes && (
              <div className="absolute right-0 top-7 z-10 bg-background rounded-lg shadow-lg border p-1 min-w-[80px]">
                {SIZE_OPTIONS.map(s => (
                  <button
                    key={s.value}
                    className={`w-full text-left px-2 py-1 text-xs rounded hover:bg-muted ${widget.size === s.value ? "text-primary font-medium" : ""}`}
                    onClick={() => { onResize(s.value); setShowSizes(false); }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button className="p-1 rounded hover:bg-red-100 text-red-500" onClick={onRemove}>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="flex-1 flex items-center">
        {renderData()}
      </div>
    </div>
  );
}

export default function DashboardBuilderPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [layouts, setLayouts] = useState<Layout[]>([]);
  const [activeLayout, setActiveLayout] = useState<Layout | null>(null);
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [dateRange, setDateRange] = useState<DateRange>("this_month");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const [showSave, setShowSave] = useState(false);
  const [newLayoutName, setNewLayoutName] = useState("");
  const [sharedRole, setSharedRole] = useState("");

  async function loadLayouts() {
    try {
      const data = await api.get("/api/dashboard-builder/layouts");
      setLayouts(data.items ?? data);
      const def = (data.items ?? data).find((l: Layout) => l.is_default);
      if (def) openLayout(def);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
    } finally {
      setLoading(false);
    }
  }

  function openLayout(layout: Layout) {
    setActiveLayout(layout);
    setWidgets(layout.widgets ?? []);
    setDateRange(layout.date_range ?? "this_month");
    fetchAllWidgetData(layout.widgets ?? [], layout.date_range ?? "this_month");
  }

  const fetchWidgetData = useCallback(async (widget: Widget, dr: DateRange): Promise<Widget> => {
    try {
      const data = await api.get(`/api/dashboard-builder/widgets/${widget.type}?date_range=${dr}`);
      return { ...widget, data: data.data, loading: false };
    } catch {
      return { ...widget, data: null, loading: false };
    }
  }, []);

  async function fetchAllWidgetData(wdgts: Widget[], dr: DateRange) {
    const withLoading = wdgts.map(w => ({ ...w, loading: true }));
    setWidgets(withLoading);
    const results = await Promise.all(withLoading.map(w => fetchWidgetData(w, dr)));
    setWidgets(results);
  }

  useEffect(() => { loadLayouts(); }, []);

  function addWidget(type: string, label: string) {
    const newWidget: Widget = {
      id: `${type}-${Date.now()}`,
      type, label, size: "1x1", loading: true,
    };
    const updated = [...widgets, newWidget];
    setWidgets(updated);
    fetchWidgetData(newWidget, dateRange).then(w => {
      setWidgets(prev => prev.map(p => p.id === newWidget.id ? w : p));
    });
    setShowLibrary(false);
  }

  function removeWidget(id: string) {
    setWidgets(prev => prev.filter(w => w.id !== id));
  }

  function resizeWidget(id: string, size: WidgetSize) {
    setWidgets(prev => prev.map(w => w.id === id ? { ...w, size } : w));
  }

  async function saveLayout() {
    setSaving(true);
    try {
      const payload = {
        name: newLayoutName || activeLayout?.name || "My Dashboard",
        widgets,
        date_range: dateRange,
        shared_role: sharedRole || undefined,
      };
      if (activeLayout) {
        await api.patch(`/api/dashboard-builder/layouts/${activeLayout.id}`, payload);
        toast.success("Dashboard saved");
      } else {
        const created = await api.post("/api/dashboard-builder/layouts", payload);
        toast.success("Dashboard created");
        await loadLayouts();
      }
      setShowSave(false);
    } catch {
      toast.error("Failed to save dashboard");
    } finally {
      setSaving(false);
    }
  }

  async function handleDateRangeChange(dr: DateRange) {
    setDateRange(dr);
    await fetchAllWidgetData(widgets, dr);
  }

  async function setAsDefault() {
    if (!activeLayout) return;
    try {
      await api.patch(`/api/dashboard-builder/layouts/${activeLayout.id}`, { is_default: true });
      toast.success("Set as default dashboard");
      loadLayouts();
    } catch {
      toast.error("Failed");
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="border-b px-6 py-3 flex items-center gap-4 bg-background">
        <LayoutDashboard className="h-5 w-5 text-primary" />
        <h1 className="font-semibold">Dashboard Builder</h1>

        {/* Layout picker */}
        <select
          className="input text-sm py-1 h-8"
          value={activeLayout?.id ?? ""}
          onChange={e => {
            const l = layouts.find(l => l.id === e.target.value);
            if (l) openLayout(l);
          }}
        >
          <option value="">— New dashboard —</option>
          {layouts.map(l => <option key={l.id} value={l.id}>{l.name}{l.is_default ? " ★" : ""}</option>)}
        </select>

        {/* Date range */}
        <select className="input text-sm py-1 h-8" value={dateRange} onChange={e => handleDateRangeChange(e.target.value as DateRange)}>
          {DATE_RANGES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>

        <div className="ml-auto flex items-center gap-2">
          {activeLayout && (
            <button className="btn-secondary text-xs flex items-center gap-1.5 h-8 px-3" onClick={setAsDefault}>
              <Star className="h-3.5 w-3.5" /> Set Default
            </button>
          )}
          <button className="btn-secondary text-xs flex items-center gap-1.5 h-8 px-3" onClick={() => setShowLibrary(true)}>
            <Plus className="h-3.5 w-3.5" /> Add Widget
          </button>
          <button className="btn-primary text-xs flex items-center gap-1.5 h-8 px-3" onClick={() => setShowSave(true)}>
            <Save className="h-3.5 w-3.5" /> Save
          </button>
        </div>
      </div>

      {/* Widget grid */}
      <div className="flex-1 overflow-y-auto p-6 bg-muted/20">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : widgets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <LayoutDashboard className="h-12 w-12 text-muted-foreground mb-3" />
            <p className="font-medium">Empty Dashboard</p>
            <p className="text-sm text-muted-foreground mt-1">Click "Add Widget" to build your view</p>
            <button className="btn-primary mt-4 flex items-center gap-2" onClick={() => setShowLibrary(true)}>
              <Plus className="h-4 w-4" /> Add First Widget
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-4 auto-rows-[160px]">
            {widgets.map(widget => (
              <WidgetCard
                key={widget.id}
                widget={widget}
                onRemove={() => removeWidget(widget.id)}
                onResize={size => resizeWidget(widget.id, size)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Widget library panel */}
      {showLibrary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Widget Library</h2>
              <button onClick={() => setShowLibrary(false)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-2">
              {WIDGET_LIBRARY.map(w => {
                const Icon = w.icon;
                return (
                  <button
                    key={w.type}
                    className="w-full flex items-center gap-3 p-3 rounded-xl border hover:bg-muted/50 text-left transition-colors"
                    onClick={() => addWidget(w.type, w.label)}
                  >
                    <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium text-sm">{w.label}</p>
                      <p className="text-xs text-muted-foreground">{w.description}</p>
                    </div>
                    <Plus className="h-4 w-4 text-muted-foreground ml-auto" />
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Save modal */}
      {showSave && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
            <h2 className="text-lg font-semibold">Save Dashboard</h2>
            <div>
              <label className="text-sm font-medium">Name</label>
              <input
                className="input mt-1 w-full"
                value={newLayoutName || activeLayout?.name || ""}
                onChange={e => setNewLayoutName(e.target.value)}
                placeholder="My Dashboard"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Share with role (optional)</label>
              <input
                className="input mt-1 w-full"
                value={sharedRole}
                onChange={e => setSharedRole(e.target.value)}
                placeholder="e.g. manager, admin"
              />
            </div>
            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setShowSave(false)}>Cancel</button>
              <button className="btn-primary flex-1 flex items-center justify-center gap-2" onClick={saveLayout} disabled={saving}>
                {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
