"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { Plus, Truck } from "lucide-react";

interface Supplier { id: string; name: string; email: string | null; phone: string | null; address: string | null; country: string; }

const EMPTY = { name: "", email: "", phone: "", address: "", country: "Sweden" };

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(false);
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
  function openEdit(s: Supplier) { setEditing(s); setForm({ name: s.name, email: s.email ?? "", phone: s.phone ?? "", address: s.address ?? "", country: s.country }); setOpen(true); }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(null);
    try {
      const body = { name: form.name, email: form.email || null, phone: form.phone || null, address: form.address || null, country: form.country };
      if (editing) await api.put(`/api/inventory/suppliers/${editing.id}`, body);
      else await api.post("/api/inventory/suppliers", body);
      setOpen(false); await load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Suppliers</h1>
          <p className="text-sm text-muted-foreground">{suppliers.length} active suppliers</p>
        </div>
        <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={openCreate}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />New supplier
        </Button>
      </div>

      {error && !open && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="space-y-2 animate-pulse">{[1, 2, 3].map((i) => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>
      ) : suppliers.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <Truck className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No suppliers yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Add your first supplier to create purchase orders.</p>
          <Button size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={openCreate}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add supplier
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden divide-y">
          {suppliers.map((s) => (
            <div key={s.id} className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="font-medium text-gray-900">{s.name}</p>
                <p className="text-sm text-muted-foreground">
                  {[s.email, s.phone, s.country].filter(Boolean).join(" · ")}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => openEdit(s)}>Edit</Button>
            </div>
          ))}
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
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
            ))}
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
