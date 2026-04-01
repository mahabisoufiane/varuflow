"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { Building2, Plus } from "lucide-react";

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
  company_name: "",
  org_number: "",
  vat_number: "",
  email: "",
  phone: "",
  address: "",
  payment_terms_days: "30",
};

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setCustomers(await api.get<Customer[]>("/api/invoicing/customers?is_active=true")); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function set(f: string, v: string) { setForm((s) => ({ ...s, [f]: v })); }

  function openCreate() { setEditing(null); setForm({ ...EMPTY }); setOpen(true); }
  function openEdit(c: Customer) {
    setEditing(c);
    setForm({
      company_name: c.company_name,
      org_number: c.org_number ?? "",
      vat_number: c.vat_number ?? "",
      email: c.email ?? "",
      phone: c.phone ?? "",
      address: c.address ?? "",
      payment_terms_days: String(c.payment_terms_days),
    });
    setOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(null);
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
      setOpen(false); await load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Customers</h1>
          <p className="text-sm text-muted-foreground">{customers.length} active customers</p>
        </div>
        <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={openCreate}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />New customer
        </Button>
      </div>

      {error && !open && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="space-y-2 animate-pulse">{[1, 2, 3].map((i) => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>
      ) : customers.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <Building2 className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No customers yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Add your first customer to start invoicing.</p>
          <Button size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={openCreate}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add customer
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden divide-y">
          {customers.map((c) => (
            <div key={c.id} className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="font-medium text-gray-900">{c.company_name}</p>
                <p className="text-sm text-muted-foreground">
                  {[c.org_number && `Org: ${c.org_number}`, c.email, `Net ${c.payment_terms_days}d`].filter(Boolean).join(" · ")}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => openEdit(c)}>Edit</Button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>{editing ? "Edit customer" : "New customer"}</DialogTitle></DialogHeader>
          <form onSubmit={handleSave} className="space-y-4 pt-2">
            {[
              { id: "company_name", label: "Company name *", placeholder: "Nordisk Handel AB", required: true },
              { id: "org_number", label: "Org number", placeholder: "556123-4567" },
              { id: "vat_number", label: "VAT number", placeholder: "SE556123456701" },
              { id: "email", label: "Email", placeholder: "orders@company.se" },
              { id: "phone", label: "Phone", placeholder: "+46 8 123 456" },
              { id: "address", label: "Address", placeholder: "Storgatan 1, Stockholm" },
            ].map(({ id, label, placeholder, required }) => (
              <div key={id} className="space-y-1.5">
                <Label htmlFor={id}>{label}</Label>
                <input id={id} required={required} value={(form as any)[id]} onChange={(e) => set(id, e.target.value)}
                  placeholder={placeholder}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
            ))}
            <div className="space-y-1.5">
              <Label htmlFor="payment_terms_days">Payment terms (days)</Label>
              <input id="payment_terms_days" type="number" min="0" max="365"
                value={form.payment_terms_days} onChange={(e) => set("payment_terms_days", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {saving ? "Saving…" : editing ? "Save changes" : "Create"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
