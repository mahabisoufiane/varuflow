"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { Plus, Truck } from "lucide-react";
import ContentPanel from "@/components/console/ContentPanel";

interface Supplier { id: string; name: string; email: string | null; phone: string | null; address: string | null; country: string; create_invoice_on_receipt?: boolean; }

const EMPTY = { name: "", email: "", phone: "", address: "", country: "Sweden", create_invoice_on_receipt: false };

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Supplier | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setSuppliers(await api.get<Supplier[]>("/api/inventory/suppliers")); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function set(f: string, v: string) { setForm((s) => ({ ...s, [f]: v })); }

  function openCreate() { setEditing(null); setForm({ ...EMPTY }); setOpen(true); }
  function openEdit(s: Supplier) { setEditing(s); setForm({ name: s.name, email: s.email ?? "", phone: s.phone ?? "", address: s.address ?? "", country: s.country, create_invoice_on_receipt: !!s.create_invoice_on_receipt }); setOpen(true); }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(null);
    try {
      const body = {
        name: form.name,
        email: form.email || null,
        phone: form.phone || null,
        address: form.address || null,
        country: form.country,
        // Item 20 — supplier-level toggle for auto-creating draft
        // payable invoices when a PO is received.
        create_invoice_on_receipt: !!form.create_invoice_on_receipt,
      };
      if (editing) await api.put(`/api/inventory/suppliers/${editing.id}`, body);
      else await api.post("/api/inventory/suppliers", body);
      setOpen(false); await load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--vf-text-primary)]">Suppliers</h1>
          <p className="text-sm text-muted-foreground">{suppliers.length} active suppliers</p>
        </div>
        <Button size="sm" className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white" onClick={openCreate}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />New supplier
        </Button>
      </div>

      {error && !open && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {!loading && suppliers.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <Truck className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No suppliers yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Add your first supplier to create purchase orders.</p>
          <Button size="sm" className="mt-4 bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white" onClick={openCreate}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add supplier
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-white">
          <ContentPanel<Supplier>
            hideHeader
            title="Suppliers"
            rows={suppliers}
            loading={loading}
            getRowId={(s) => s.id}
            columns={[
              { key: "name", header: "Name", render: (s) => <span className="font-medium text-foreground">{s.name}</span> },
              { key: "email", header: "Email", render: (s) => s.email ?? "—" },
              { key: "phone", header: "Phone", render: (s) => s.phone ?? "—" },
              { key: "country", header: "Country", render: (s) => s.country },
            ]}
            selected={selected}
            onSelect={setSelected}
            detailTitle={(s) => s.name}
            renderDetail={(s) => (
              <div className="space-y-4">
                <dl className="divide-y">
                  {([
                    ["Email", s.email],
                    ["Phone", s.phone],
                    ["Address", s.address],
                    ["Country", s.country],
                    ["Auto-invoice on receipt", s.create_invoice_on_receipt ? "Yes" : "No"],
                  ] as [string, string | null][]).map(([label, val]) => (
                    <div key={label} className="grid grid-cols-3 gap-2 py-2.5">
                      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                      <dd className="col-span-2 text-sm text-foreground">{val || "—"}</dd>
                    </div>
                  ))}
                </dl>
                <Button variant="outline" size="sm" onClick={() => { setSelected(null); openEdit(s); }}>Edit</Button>
              </div>
            )}
          />
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>{editing ? "Edit supplier" : "New supplier"}</DialogTitle></DialogHeader>
          <form onSubmit={handleSave} className="space-y-4 pt-2">
            {[
              { id: "name", label: "Name *", placeholder: "Nordic Foods AB", required: true },
              { id: "email", label: "Email", placeholder: "orders@supplier.se" },
              { id: "phone", label: "Phone", placeholder: "+46 8 123 456" },
              { id: "address", label: "Address", placeholder: "Leveransvägen 1, Stockholm" },
              { id: "country", label: "Country", placeholder: "Sweden" },
            ].map(({ id, label, placeholder, required }) => (
              <div key={id} className="space-y-1.5">
                <Label htmlFor={id}>{label}</Label>
                <input id={id} required={required} value={(form as any)[id]} onChange={(e) => set(id, e.target.value)} placeholder={placeholder}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[var(--vf-brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
              </div>
            ))}
            <div className="flex items-start gap-3 rounded-md border bg-gray-50 px-3 py-2">
              <input
                id="create_invoice_on_receipt"
                type="checkbox"
                checked={!!form.create_invoice_on_receipt}
                onChange={(e) => setForm((s) => ({ ...s, create_invoice_on_receipt: e.target.checked }))}
                className="mt-0.5 h-4 w-4 rounded border-gray-300"
              />
              <div className="text-sm">
                <label htmlFor="create_invoice_on_receipt" className="font-medium text-gray-900 cursor-pointer">
                  Auto-create payable invoice on PO receipt
                </label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  When a purchase order from this supplier is received, a draft
                  payable invoice is created. Nothing is sent automatically — you
                  review and approve before paying.
                </p>
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={saving} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
                {saving ? "Saving…" : editing ? "Save changes" : "Create"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
