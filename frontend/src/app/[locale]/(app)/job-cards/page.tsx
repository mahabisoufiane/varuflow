"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Plus, Wrench, AlertCircle, ChevronRight, Clock, CheckCircle } from "lucide-react";

interface JobCardPart { id: string; description: string; quantity: number; unit_price: number; product_id: string | null; }
interface JobCardLabour { id: string; staff_name: string | null; hours: number; hourly_rate: number; notes: string | null; }
interface JobCardPhoto { id: string; url: string; caption: string | null; photo_type: string; }

interface JobCard {
  id: string;
  job_number: string;
  customer_id: string | null;
  customer_name?: string | null;
  assigned_staff_id: string | null;
  title: string;
  description: string | null;
  site_address: string | null;
  scheduled_date: string | null;
  estimated_hours: number | null;
  status: string;
  customer_signature_url: string | null;
  signed_at: string | null;
  invoice_id: string | null;
  currency: string;
  notes: string | null;
  parts: JobCardPart[];
  labour: JobCardLabour[];
  photos: JobCardPhoto[];
  created_at: string;
}

const STATUSES = ["pending", "assigned", "in_progress", "completed", "invoiced"] as const;

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending", assigned: "Assigned", in_progress: "In Progress",
  completed: "Completed", invoiced: "Invoiced",
};

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  assigned: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  invoiced: "bg-purple-100 text-purple-700",
};

export default function JobCardsPage() {
  const router = useRouter();
  const [cards, setCards] = useState<JobCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<JobCard | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [form, setForm] = useState({
    title: "", description: "", customer_id: "", assigned_staff_id: "",
    site_address: "", scheduled_date: "", estimated_hours: "", currency: "SEK", notes: "",
  });
  const [saving, setSaving] = useState(false);

  // Sub-form state for selected card
  const [partForm, setPartForm] = useState({ description: "", quantity: "1", unit_price: "" });
  const [labourForm, setLabourForm] = useState({ staff_name: "", hours: "", hourly_rate: "" });
  const [photoForm, setPhotoForm] = useState({ url: "", caption: "", photo_type: "before" });
  const [sigUrl, setSigUrl] = useState("");
  const [subTab, setSubTab] = useState<"parts" | "labour" | "photos" | "actions">("parts");

  async function load() {
    setLoading(true);
    try {
      const params = statusFilter ? `?status=${statusFilter}` : "";
      const data = await api.get(`/api/job-cards${params}`);
      setCards(Array.isArray(data) ? data : []);
    } catch (e: any) {
      if (e?.status === 401) { router.push("/auth/login"); return; }
      setError("Failed to load job cards");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [statusFilter]);

  async function create() {
    if (!form.title.trim()) { alert("Title required"); return; }
    setSaving(true);
    try {
      const body: Record<string, unknown> = { title: form.title, currency: form.currency };
      if (form.description) body.description = form.description;
      if (form.customer_id) body.customer_id = form.customer_id;
      if (form.assigned_staff_id) body.assigned_staff_id = form.assigned_staff_id;
      if (form.site_address) body.site_address = form.site_address;
      if (form.scheduled_date) body.scheduled_date = form.scheduled_date;
      if (form.estimated_hours) body.estimated_hours = parseFloat(form.estimated_hours);
      if (form.notes) body.notes = form.notes;
      const data = await api.post("/api/job-cards", body);
      setCards(prev => [data, ...prev]);
      setShowForm(false);
      setForm({ title: "", description: "", customer_id: "", assigned_staff_id: "", site_address: "", scheduled_date: "", estimated_hours: "", currency: "SEK", notes: "" });
      setSelected(data);
    } catch { alert("Failed to create job card"); }
    finally { setSaving(false); }
  }

  async function updateStatus(card: JobCard, status: string) {
    try {
      const data = await api.patch(`/api/job-cards/${card.id}`, { status });
      setCards(prev => prev.map(c => c.id === card.id ? data : c));
      setSelected(data);
    } catch { alert("Failed to update status"); }
  }

  async function addPart(cardId: string) {
    if (!partForm.description || !partForm.unit_price) return;
    try {
      const data = await api.post(`/api/job-cards/${cardId}/parts`, {
        description: partForm.description, quantity: parseFloat(partForm.quantity) || 1,
        unit_price: parseFloat(partForm.unit_price),
      });
      setCards(prev => prev.map(c => c.id === cardId ? data : c));
      setSelected(data);
      setPartForm({ description: "", quantity: "1", unit_price: "" });
    } catch { alert("Failed to add part"); }
  }

  async function deletePart(cardId: string, partId: string) {
    try {
      await api.delete(`/api/job-cards/${cardId}/parts/${partId}`);
      await refreshCard(cardId);
    } catch { alert("Failed to delete part"); }
  }

  async function addLabour(cardId: string) {
    if (!labourForm.hours || !labourForm.hourly_rate) return;
    try {
      const data = await api.post(`/api/job-cards/${cardId}/labour`, {
        staff_name: labourForm.staff_name || null,
        hours: parseFloat(labourForm.hours),
        hourly_rate: parseFloat(labourForm.hourly_rate),
      });
      setCards(prev => prev.map(c => c.id === cardId ? data : c));
      setSelected(data);
      setLabourForm({ staff_name: "", hours: "", hourly_rate: "" });
    } catch { alert("Failed to add labour"); }
  }

  async function deleteLabour(cardId: string, labourId: string) {
    try {
      await api.delete(`/api/job-cards/${cardId}/labour/${labourId}`);
      await refreshCard(cardId);
    } catch { alert("Failed to delete labour entry"); }
  }

  async function addPhoto(cardId: string) {
    if (!photoForm.url) return;
    try {
      const data = await api.post(`/api/job-cards/${cardId}/photos`, photoForm);
      setCards(prev => prev.map(c => c.id === cardId ? data : c));
      setSelected(data);
      setPhotoForm({ url: "", caption: "", photo_type: "before" });
    } catch { alert("Failed to add photo"); }
  }

  async function signCard(cardId: string) {
    if (!sigUrl) return;
    try {
      const data = await api.post(`/api/job-cards/${cardId}/sign`, { signature_url: sigUrl });
      setCards(prev => prev.map(c => c.id === cardId ? data : c));
      setSelected(data);
      setSigUrl("");
    } catch { alert("Failed to record signature"); }
  }

  async function generateInvoice(cardId: string) {
    if (!confirm("Generate invoice from this job card (parts + labour)?")) return;
    try {
      const data = await api.post(`/api/job-cards/${cardId}/invoice`, {});
      alert(`Invoice created: ${data.invoice_number} — ${data.total_sek?.toLocaleString()} SEK`);
      await refreshCard(cardId);
    } catch (e: any) {
      alert(e?.data?.detail ?? "Failed to generate invoice");
    }
  }

  async function refreshCard(cardId: string) {
    try {
      const data = await api.get(`/api/job-cards/${cardId}`);
      setCards(prev => prev.map(c => c.id === cardId ? data : c));
      setSelected(data);
    } catch {}
  }

  function calcTotal(card: JobCard) {
    const parts = card.parts.reduce((s, p) => s + p.quantity * p.unit_price, 0);
    const labour = card.labour.reduce((s, l) => s + l.hours * l.hourly_rate, 0);
    return parts + labour;
  }

  if (loading) return <div className="p-8 text-center text-gray-400">Loading…</div>;

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wrench className="w-5 h-5 text-indigo-600" />
          <h1 className="text-xl font-bold text-gray-900">Job Cards</h1>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="btn-primary flex items-center gap-1 text-sm">
          <Plus className="w-4 h-4" /> New Job Card
        </button>
      </div>

      {error && <div className="text-red-600 text-sm flex gap-2"><AlertCircle className="w-4 h-4 mt-0.5" />{error}</div>}

      {/* Create form */}
      {showForm && (
        <div className="rounded-xl border bg-white shadow-sm p-5 space-y-4">
          <h2 className="font-semibold text-gray-800">New Job Card</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Title *</label>
              <input className="input w-full" placeholder="e.g. HVAC service call — customer ABC" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Description</label>
              <textarea className="input w-full" rows={2} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Scheduled date</label>
              <input type="date" className="input w-full" value={form.scheduled_date} onChange={e => setForm(f => ({ ...f, scheduled_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Estimated hours</label>
              <input type="number" className="input w-full" placeholder="2.5" value={form.estimated_hours} onChange={e => setForm(f => ({ ...f, estimated_hours: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Site address (if different from billing)</label>
              <input className="input w-full" placeholder="Street address, city" value={form.site_address} onChange={e => setForm(f => ({ ...f, site_address: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={create} disabled={saving} className="btn-primary text-sm">{saving ? "Creating…" : "Create"}</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Status filter */}
      <div className="flex gap-1 flex-wrap">
        {["", ...STATUSES].map(s => (
          <button
            key={s || "all"}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${statusFilter === s ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"}`}
          >
            {s ? STATUS_LABELS[s] ?? s : "All"}
          </button>
        ))}
      </div>

      {/* Two-pane layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* List */}
        <div className="w-80 shrink-0 space-y-2 overflow-y-auto">
          {cards.length === 0 && <div className="text-center text-gray-400 py-12">No job cards found.</div>}
          {cards.map(card => (
            <div
              key={card.id}
              onClick={() => { setSelected(card); setSubTab("parts"); }}
              className={`rounded-xl border bg-white shadow-sm p-4 cursor-pointer hover:shadow-md transition-shadow ${selected?.id === card.id ? "ring-2 ring-indigo-400" : ""}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-400 font-mono">{card.job_number}</p>
                  <p className="font-semibold text-gray-900 leading-tight mt-0.5 truncate">{card.title}</p>
                  {card.customer_name && <p className="text-xs text-gray-500 mt-0.5">{card.customer_name}</p>}
                  {card.scheduled_date && <p className="text-xs text-gray-400 flex items-center gap-1 mt-1"><Clock className="w-3 h-3" />{card.scheduled_date}</p>}
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0 ml-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[card.status] ?? "bg-gray-100 text-gray-600"}`}>{STATUS_LABELS[card.status] ?? card.status}</span>
                  {card.invoice_id && <span className="text-xs text-purple-600">Invoiced</span>}
                </div>
              </div>
              {(card.parts.length > 0 || card.labour.length > 0) && (
                <p className="text-xs text-gray-500 mt-2 font-medium">{calcTotal(card).toLocaleString()} {card.currency}</p>
              )}
            </div>
          ))}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="flex-1 rounded-xl border bg-white shadow-sm overflow-y-auto">
            <div className="p-5 border-b flex items-start justify-between">
              <div>
                <p className="text-xs text-gray-400 font-mono">{selected.job_number}</p>
                <h2 className="text-lg font-bold text-gray-900 mt-0.5">{selected.title}</h2>
                {selected.description && <p className="text-sm text-gray-600 mt-1">{selected.description}</p>}
                {selected.site_address && <p className="text-xs text-gray-500 mt-1">📍 {selected.site_address}</p>}
                {selected.notes && <p className="text-xs text-gray-500 mt-1">💬 {selected.notes}</p>}
              </div>
              <div className="flex flex-col items-end gap-2 ml-4 shrink-0">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_BADGE[selected.status] ?? "bg-gray-100"}`}>{STATUS_LABELS[selected.status] ?? selected.status}</span>
                {/* Status actions */}
                {selected.status === "pending" && (
                  <button onClick={() => updateStatus(selected, "assigned")} className="text-xs py-1 px-3 rounded bg-blue-600 text-white hover:bg-blue-700">Mark Assigned</button>
                )}
                {selected.status === "assigned" && (
                  <button onClick={() => updateStatus(selected, "in_progress")} className="text-xs py-1 px-3 rounded bg-yellow-500 text-white hover:bg-yellow-600">Start Job</button>
                )}
                {selected.status === "in_progress" && (
                  <button onClick={() => updateStatus(selected, "completed")} className="text-xs py-1 px-3 rounded bg-green-600 text-white hover:bg-green-700">Complete</button>
                )}
                {selected.status === "completed" && !selected.invoice_id && (
                  <button onClick={() => generateInvoice(selected.id)} className="text-xs py-1 px-3 rounded bg-purple-600 text-white hover:bg-purple-700">Generate Invoice</button>
                )}
              </div>
            </div>

            {/* Sub-tabs */}
            <div className="border-b flex">
              {(["parts", "labour", "photos", "actions"] as const).map(t => (
                <button key={t} onClick={() => setSubTab(t)} className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors capitalize ${subTab === t ? "border-indigo-600 text-indigo-700" : "border-transparent text-gray-500 hover:text-gray-700"}`}>{t}</button>
              ))}
            </div>

            <div className="p-5">
              {subTab === "parts" && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-gray-700">Parts used</h3>
                  {selected.parts.length > 0 && (
                    <div className="text-sm divide-y border rounded overflow-hidden">
                      {selected.parts.map(p => (
                        <div key={p.id} className="flex items-center justify-between px-3 py-2">
                          <span className="text-gray-700">{p.description} × {p.quantity}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-gray-500">{(p.quantity * p.unit_price).toLocaleString()} {selected.currency}</span>
                            <button onClick={() => deletePart(selected.id, p.id)} className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
                          </div>
                        </div>
                      ))}
                      <div className="px-3 py-2 bg-gray-50 font-medium text-sm flex justify-between">
                        <span>Parts total</span>
                        <span>{selected.parts.reduce((s, p) => s + p.quantity * p.unit_price, 0).toLocaleString()} {selected.currency}</span>
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-[1fr_80px_100px_auto] gap-2 items-end pt-2">
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Description</label>
                      <input className="input text-sm" placeholder="Part name" value={partForm.description} onChange={e => setPartForm(f => ({ ...f, description: e.target.value }))} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Qty</label>
                      <input type="number" className="input text-sm" value={partForm.quantity} onChange={e => setPartForm(f => ({ ...f, quantity: e.target.value }))} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Unit price</label>
                      <input type="number" className="input text-sm" placeholder="0.00" value={partForm.unit_price} onChange={e => setPartForm(f => ({ ...f, unit_price: e.target.value }))} />
                    </div>
                    <button onClick={() => addPart(selected.id)} className="btn-primary text-sm self-end">Add</button>
                  </div>
                </div>
              )}

              {subTab === "labour" && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-gray-700">Labour recorded</h3>
                  {selected.labour.length > 0 && (
                    <div className="text-sm divide-y border rounded overflow-hidden">
                      {selected.labour.map(l => (
                        <div key={l.id} className="flex items-center justify-between px-3 py-2">
                          <span className="text-gray-700">{l.staff_name || "Staff"} — {l.hours}h @ {l.hourly_rate}/h{l.notes ? ` (${l.notes})` : ""}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-gray-500">{(l.hours * l.hourly_rate).toLocaleString()} {selected.currency}</span>
                            <button onClick={() => deleteLabour(selected.id, l.id)} className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
                          </div>
                        </div>
                      ))}
                      <div className="px-3 py-2 bg-gray-50 font-medium text-sm flex justify-between">
                        <span>Labour total</span>
                        <span>{selected.labour.reduce((s, l) => s + l.hours * l.hourly_rate, 0).toLocaleString()} {selected.currency}</span>
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-[1fr_80px_100px_auto] gap-2 items-end pt-2">
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Staff name</label>
                      <input className="input text-sm" placeholder="Name" value={labourForm.staff_name} onChange={e => setLabourForm(f => ({ ...f, staff_name: e.target.value }))} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Hours</label>
                      <input type="number" step="0.25" className="input text-sm" placeholder="0.00" value={labourForm.hours} onChange={e => setLabourForm(f => ({ ...f, hours: e.target.value }))} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Hourly rate</label>
                      <input type="number" className="input text-sm" placeholder="0.00" value={labourForm.hourly_rate} onChange={e => setLabourForm(f => ({ ...f, hourly_rate: e.target.value }))} />
                    </div>
                    <button onClick={() => addLabour(selected.id)} className="btn-primary text-sm self-end">Add</button>
                  </div>
                  {(selected.parts.length + selected.labour.length) > 0 && (
                    <div className="mt-4 p-3 bg-indigo-50 rounded-lg text-sm font-semibold text-indigo-700 flex justify-between">
                      <span>Job total (ex VAT)</span>
                      <span>{calcTotal(selected).toLocaleString()} {selected.currency}</span>
                    </div>
                  )}
                </div>
              )}

              {subTab === "photos" && (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-gray-700">Photos</h3>
                  {selected.photos.length > 0 && (
                    <div className="grid grid-cols-3 gap-2">
                      {selected.photos.map(ph => (
                        <div key={ph.id} className="relative group rounded-lg overflow-hidden border aspect-video bg-gray-50">
                          <img src={ph.url} alt={ph.caption ?? ph.photo_type} className="w-full h-full object-cover" onError={e => { (e.target as HTMLImageElement).src = ""; }} />
                          <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 flex justify-between">
                            <span>{ph.photo_type}</span>
                            {ph.caption && <span className="truncate ml-1">{ph.caption}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {selected.photos.length === 0 && <p className="text-sm text-gray-400">No photos attached.</p>}
                  <div className="grid grid-cols-[1fr_80px_80px_auto] gap-2 items-end">
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Photo URL</label>
                      <input className="input text-sm" placeholder="https://…" value={photoForm.url} onChange={e => setPhotoForm(f => ({ ...f, url: e.target.value }))} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Type</label>
                      <select className="input text-sm" value={photoForm.photo_type} onChange={e => setPhotoForm(f => ({ ...f, photo_type: e.target.value }))}>
                        <option value="before">Before</option>
                        <option value="after">After</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Caption</label>
                      <input className="input text-sm" placeholder="Optional" value={photoForm.caption} onChange={e => setPhotoForm(f => ({ ...f, caption: e.target.value }))} />
                    </div>
                    <button onClick={() => addPhoto(selected.id)} className="btn-primary text-sm self-end">Add</button>
                  </div>
                </div>
              )}

              {subTab === "actions" && (
                <div className="space-y-4">
                  {/* Signature */}
                  <div className="p-4 rounded-lg border space-y-3">
                    <h3 className="text-sm font-semibold text-gray-700">Customer signature</h3>
                    {selected.customer_signature_url ? (
                      <div>
                        <p className="text-xs text-green-600 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Signed {selected.signed_at ? new Date(selected.signed_at).toLocaleString() : ""}</p>
                        <a href={selected.customer_signature_url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 hover:underline mt-1 block">View signature</a>
                      </div>
                    ) : (
                      <div className="flex gap-2 items-end">
                        <div className="flex-1">
                          <label className="text-xs text-gray-500 mb-1 block">Signature image URL</label>
                          <input className="input w-full text-sm" placeholder="https://…" value={sigUrl} onChange={e => setSigUrl(e.target.value)} />
                        </div>
                        <button onClick={() => signCard(selected.id)} disabled={!sigUrl} className="btn-primary text-sm">Record</button>
                      </div>
                    )}
                  </div>

                  {/* Generate invoice */}
                  {selected.status !== "invoiced" && (
                    <div className="p-4 rounded-lg border space-y-2">
                      <h3 className="text-sm font-semibold text-gray-700">Generate invoice</h3>
                      <p className="text-xs text-gray-500">Creates a DRAFT invoice from all parts and labour on this job card.</p>
                      <button
                        onClick={() => generateInvoice(selected.id)}
                        disabled={selected.status !== "completed"}
                        className="btn-primary text-sm disabled:opacity-50"
                      >
                        {selected.status !== "completed" ? "Complete job first" : "Generate Invoice"}
                      </button>
                    </div>
                  )}

                  {selected.invoice_id && (
                    <p className="text-sm text-purple-700 font-medium flex items-center gap-1"><CheckCircle className="w-4 h-4" /> Invoice {selected.invoice_id.slice(0, 8)}… created</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
