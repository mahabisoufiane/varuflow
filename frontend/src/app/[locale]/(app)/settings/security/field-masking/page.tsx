"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Eye, EyeOff, Trash2, Plus, Wand2 } from "lucide-react";

interface Rule { id: string; role: string; resource: string; field: string; mask_style: string; enabled: boolean }
interface PreviewResult { original: Record<string, unknown>; masked: Record<string, unknown> }

const ROLES = ["member", "viewer", "accountant"];
const RESOURCES = ["invoice", "customer", "supplier", "expense", "payroll"];
const FIELDS: Record<string, string[]> = {
  invoice:  ["total_amount", "subtotal", "tax_amount", "paid_amount"],
  customer: ["email", "phone", "name", "bank_account"],
  supplier: ["email", "phone", "name"],
  expense:  ["amount"],
  payroll:  ["salary", "net_pay"],
};
const STYLES = ["obfuscate", "partial", "hidden"];

const SAMPLE_DATA: Record<string, Record<string, unknown>> = {
  invoice:  { total_amount: "12345.00", subtotal: "10000.00", tax_amount: "2345.00" },
  customer: { email: "john.smith@acme.com", phone: "+46 70 123 45 67", name: "John Smith" },
  supplier: { email: "purchasing@supplier.se", phone: "+46 8 555 0100", name: "Nordic Supplies AB" },
  expense:  { amount: "4999.00" },
  payroll:  { salary: "55000.00", net_pay: "42000.00" },
};

export default function FieldMaskingPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [rules, setRules] = useState<Rule[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [prevRole, setPrevRole] = useState("member");
  const [prevResource, setPrevResource] = useState("invoice");
  const [form, setForm] = useState({ role: "member", resource: "invoice", field: "total_amount", mask_style: "obfuscate" });

  const fetch_ = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function load() {
    const res = await fetch_("/api/compliance/field-masking");
    if (res.ok) setRules((await res.json()).rules);
  }

  useEffect(() => { load(); }, []);

  async function installDefaults() {
    const res = await fetch_("/api/compliance/field-masking/defaults", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      toast.success(data.message);
      await load();
    } else toast.error("Failed");
  }

  async function addRule() {
    const res = await fetch_("/api/compliance/field-masking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      toast.success("Rule saved");
      setShowForm(false);
      await load();
    } else {
      const err = await res.json();
      toast.error(err.detail || "Failed");
    }
  }

  async function deleteRule(id: string) {
    await fetch_(`/api/compliance/field-masking/${id}`, { method: "DELETE" });
    setRules(r => r.filter(x => x.id !== id));
    toast.success("Rule removed");
  }

  async function loadPreview() {
    const sample = SAMPLE_DATA[prevResource] || {};
    const res = await fetch_("/api/compliance/field-masking/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resource: prevResource, role: prevRole, sample }),
    });
    if (res.ok) setPreview(await res.json());
  }

  const styleColor: Record<string, string> = {
    obfuscate: "bg-amber-50 text-amber-700",
    partial: "bg-blue-50 text-blue-700",
    hidden: "bg-red-50 text-red-600",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Field Masking</h1>
          <p className="mt-1 text-sm text-gray-500">Control which fields are masked for MEMBER and VIEWER roles.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={installDefaults} className="btn-secondary flex items-center gap-1.5">
            <Wand2 className="h-3.5 w-3.5" /> Install Defaults
          </button>
          <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1.5">
            <Plus className="h-3.5 w-3.5" /> Add Rule
          </button>
        </div>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[["Role", "role", ROLES], ["Resource", "resource", RESOURCES], ["Mask Style", "mask_style", STYLES]] .map(([label, key, opts]) => (
              <div key={key as string}>
                <label className="text-xs font-medium text-gray-700 mb-1 block">{label as string}</label>
                <select className="input w-full capitalize" value={(form as Record<string, string>)[key as string]}
                  onChange={e => {
                    const newForm = { ...form, [key as string]: e.target.value };
                    if (key === "resource") newForm.field = FIELDS[e.target.value]?.[0] || "";
                    setForm(newForm);
                  }}>
                  {(opts as string[]).map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
            ))}
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Field</label>
              <select className="input w-full" value={form.field} onChange={e => setForm(f => ({ ...f, field: e.target.value }))}>
                {(FIELDS[form.resource] || []).map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={addRule} className="btn-primary">Save Rule</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {/* Rules list */}
      {rules.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
          No masking rules. Click <strong>Install Defaults</strong> for Varuflow's recommended settings.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {rules.map(r => (
            <div key={r.id} className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3">
              {r.enabled ? <Eye className="h-4 w-4 text-blue-400" /> : <EyeOff className="h-4 w-4 text-gray-300" />}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 capitalize">
                  {r.role} · {r.resource} · <span className="text-blue-700">{r.field}</span>
                </p>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${styleColor[r.mask_style]}`}>{r.mask_style}</span>
              </div>
              <button onClick={() => deleteRule(r.id)} className="btn-sm-danger-outline">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Live preview */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Live Preview</h2>
        <div className="flex gap-3">
          <select className="input" value={prevRole} onChange={e => { setPrevRole(e.target.value); setPreview(null); }}>
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <select className="input" value={prevResource} onChange={e => { setPrevResource(e.target.value); setPreview(null); }}>
            {RESOURCES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <button onClick={loadPreview} className="btn-primary">Preview</button>
        </div>
        {preview && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">Original (Admin view)</p>
              <pre className="bg-gray-50 rounded-lg p-3 text-xs overflow-auto">{JSON.stringify(preview.original, null, 2)}</pre>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2 capitalize">{prevRole} view (masked)</p>
              <pre className="bg-amber-50 rounded-lg p-3 text-xs overflow-auto border border-amber-200">{JSON.stringify(preview.masked, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
