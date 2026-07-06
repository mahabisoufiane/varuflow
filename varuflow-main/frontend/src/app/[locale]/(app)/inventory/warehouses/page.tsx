"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useEffect, useState } from "react";
import { Plus, Warehouse } from "lucide-react";
import ContentPanel from "@/components/console/ContentPanel";

interface WarehouseItem {
  id: string; name: string; location: string | null; is_active: boolean;
}

export default function WarehousesPage() {
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<WarehouseItem | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<WarehouseItem | null>(null);
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<WarehouseItem[]>("/api/inventory/warehouses");
      setWarehouses(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setEditing(null); setName(""); setLocation(""); setOpen(true);
  }

  function openEdit(w: WarehouseItem) {
    setEditing(w); setName(w.name); setLocation(w.location ?? ""); setOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        await api.put(`/api/inventory/warehouses/${editing.id}`, { name, location: location || null });
      } else {
        await api.post("/api/inventory/warehouses", { name, location: location || null });
      }
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Warehouses</h1>
          <p className="text-sm text-muted-foreground">Manage storage locations</p>
        </div>
        <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={openCreate}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />New warehouse
        </Button>
      </div>

      {error && !open && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>
      )}

      {!loading && warehouses.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <Warehouse className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No warehouses yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Add your first warehouse to start tracking stock.</p>
          <Button size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={openCreate}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add warehouse
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-white">
          <ContentPanel<WarehouseItem>
            hideHeader
            title="Warehouses"
            rows={warehouses}
            loading={loading}
            getRowId={(w) => w.id}
            columns={[
              { key: "name", header: "Name", render: (w) => <span className="font-medium text-foreground">{w.name}</span> },
              { key: "location", header: "Location", render: (w) => w.location ?? "—" },
              { key: "is_active", header: "Status", render: (w) => w.is_active ? "Active" : "Inactive" },
            ]}
            selected={selected}
            onSelect={setSelected}
            detailTitle={(w) => w.name}
            renderDetail={(w) => (
              <div className="space-y-4">
                <dl className="divide-y">
                  {([
                    ["Location", w.location || "—"],
                    ["Status", w.is_active ? "Active" : "Inactive"],
                  ] as [string, string][]).map(([label, val]) => (
                    <div key={label} className="grid grid-cols-3 gap-2 py-2.5">
                      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                      <dd className="col-span-2 text-sm text-foreground">{val}</dd>
                    </div>
                  ))}
                </dl>
                <Button variant="outline" size="sm" onClick={() => { setSelected(null); openEdit(w); }}>Edit</Button>
              </div>
            )}
          />
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit warehouse" : "New warehouse"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSave} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="wh-name">Name *</Label>
              <input id="wh-name" required value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Stockholm — Main" className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wh-loc">Location</Label>
              <input id="wh-loc" value={location} onChange={(e) => setLocation(e.target.value)}
                placeholder="Industrivägen 5, Stockholm" className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
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
