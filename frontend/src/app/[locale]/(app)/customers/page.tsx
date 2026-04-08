"use client";

import { api } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Building2, Mail, Phone, Plus, Search, FileText, ArrowRight, X,
} from "lucide-react";

interface Customer {
  id: string;
  company_name: string;
  org_number: string | null;
  vat_number: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  payment_terms_days: number;
  is_active: boolean;
}

const EMPTY = {
  company_name: "", org_number: "", vat_number: "",
  email: "", phone: "", address: "", payment_terms_days: "30",
};

function Avatar({ name }: { name: string }) {
  const initials = name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const colors = [
    "from-blue-500 to-indigo-600",
    "from-emerald-500 to-teal-600",
    "from-violet-500 to-purple-600",
    "from-amber-500 to-orange-600",
    "from-rose-500 to-pink-600",
    "from-cyan-500 to-blue-600",
  ];
  const color = colors[name.charCodeAt(0) % colors.length];
  return (
    <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${color} text-[13px] font-bold text-white shadow-sm`}>
      {initials}
    </div>
  );
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function load() {
    try { setCustomers(await api.get<Customer[]>("/api/invoicing/customers?is_active=true")); }
    catch (e: unknown) { toast.error((e as Error).message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function set(f: string, v: string) { setForm(s => ({ ...s, [f]: v })); }

  function openCreate() { setEditing(null); setForm({ ...EMPTY }); setFormError(null); setOpen(true); }
  function openEdit(c: Customer) {
    setEditing(c);
    setForm({
      company_name: c.company_name, org_number: c.org_number ?? "",
      vat_number: c.vat_number ?? "", email: c.email ?? "",
      phone: c.phone ?? "", address: c.address ?? "",
      payment_terms_days: String(c.payment_terms_days),
    });
    setFormError(null); setOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setFormError(null);
    try {
      const body = {
        company_name: form.company_name,
        org_number: form.org_number || null,
        vat_number: form.vat_number || null,
        email: form.email || null,
        phone: form.phone || null,
        address: form.address || null,
        payment_terms_days: Number(form.payment_terms_days),
      };
      if (editing) await api.put(`/api/invoicing/customers/${editing.id}`, body);
      else await api.post("/api/invoicing/customers", body);
      toast.success(editing ? "Customer updated" : "Customer created");
      setOpen(false); await load();
    } catch (e: unknown) { setFormError((e as Error).message); }
    finally { setSaving(false); }
  }

  const filtered = customers.filter(c =>
    c.company_name.toLowerCase().includes(search.toLowerCase()) ||
    (c.email ?? "").toLowerCase().includes(search.toLowerCase()) ||
    (c.org_number ?? "").includes(search)
  );

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-gray-900">Customers</h1>
          <p className="text-xs text-gray-400 mt-0.5">{customers.length} active customers</p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-[#161b22] transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />New customer
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, email, or org number…"
          className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-9 pr-4 text-sm text-gray-700 placeholder-gray-400 shadow-sm outline-none focus:border-gray-400 transition-colors"
        />
        {search && (
          <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2">
            <X className="h-4 w-4 text-gray-400 hover:text-gray-600" />
          </button>
        )}
      </div>

      {/* List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[1,2,3,4].map(i => (
            <div key={i} className="h-24 animate-pulse rounded-2xl bg-gray-100" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-white px-6 py-20 text-center">
          <Building2 className="mx-auto h-10 w-10 text-gray-200" />
          <p className="mt-3 text-sm font-semibold text-gray-500">
            {search ? "No customers match your search" : "No customers yet"}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {search ? "Try a different search term" : "Add your first customer to start invoicing."}
          </p>
          {!search && (
            <button
              onClick={openCreate}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-4 py-2 text-sm font-medium text-white hover:bg-[#161b22]"
            >
              <Plus className="h-3.5 w-3.5" />Add customer
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map(c => (
            <div
              key={c.id}
              className="group flex items-start gap-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm hover:border-gray-300 hover:shadow-md transition-all"
            >
              <Avatar name={c.company_name} />
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-gray-900 leading-tight">{c.company_name}</p>
                  <span className="shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-500">
                    Net {c.payment_terms_days}d
                  </span>
                </div>

                <div className="mt-2 space-y-1">
                  {c.email && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <Mail className="h-3 w-3 shrink-0 text-gray-400" />{c.email}
                    </div>
                  )}
                  {c.phone && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <Phone className="h-3 w-3 shrink-0 text-gray-400" />{c.phone}
                    </div>
                  )}
                  {c.org_number && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <Building2 className="h-3 w-3 shrink-0 text-gray-400" />Org {c.org_number}
                    </div>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => openEdit(c)}
                    className="rounded-lg border border-gray-200 px-2.5 py-1 text-[11px] font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    Edit
                  </button>
                  <a
                    href={`/invoices/new?customer=${c.id}`}
                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600 hover:bg-blue-100 transition-colors"
                  >
                    <FileText className="h-3 w-3" />Invoice
                  </a>
                  <a
                    href={`/invoices?customer=${c.id}`}
                    className="ml-auto inline-flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-700 transition-colors"
                  >
                    History <ArrowRight className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? `Edit ${editing.company_name}` : "New customer"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSave} className="space-y-4 pt-1">
            <div className="grid grid-cols-2 gap-3">
              {[
                { id: "company_name", label: "Company name *", span: true,  required: true,  placeholder: "Nordisk Handel AB"    },
                { id: "org_number",   label: "Org number",     span: false, required: false, placeholder: "556123-4567"           },
                { id: "vat_number",   label: "VAT number",     span: false, required: false, placeholder: "SE556123456701"        },
                { id: "email",        label: "Email",          span: false, required: false, placeholder: "orders@company.se"     },
                { id: "phone",        label: "Phone",          span: false, required: false, placeholder: "+46 8 123 456"         },
                { id: "address",      label: "Address",        span: true,  required: false, placeholder: "Storgatan 1, Stockholm"},
              ].map(({ id, label, span, required, placeholder }) => (
                <div key={id} className={`space-y-1 ${span ? "col-span-2" : ""}`}>
                  <Label htmlFor={id} className="text-xs">{label}</Label>
                  <input
                    id={id} required={required}
                    value={(form as Record<string, string>)[id]}
                    onChange={e => set(id, e.target.value)}
                    placeholder={placeholder}
                    className="block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm focus:border-gray-400 focus:bg-white focus:outline-none transition-colors"
                  />
                </div>
              ))}
              <div className="space-y-1">
                <Label htmlFor="payment_terms_days" className="text-xs">Payment terms (days)</Label>
                <input
                  id="payment_terms_days" type="number" min="0" max="365"
                  value={form.payment_terms_days} onChange={e => set("payment_terms_days", e.target.value)}
                  className="block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm focus:border-gray-400 focus:bg-white focus:outline-none transition-colors"
                />
              </div>
            </div>
            {formError && <p className="text-xs text-red-600">{formError}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setOpen(false)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">
                Cancel
              </button>
              <button type="submit" disabled={saving}
                className="rounded-lg bg-[#0d1117] px-4 py-2 text-sm font-medium text-white hover:bg-[#161b22] disabled:opacity-50">
                {saving ? "Saving…" : editing ? "Save changes" : "Create customer"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
