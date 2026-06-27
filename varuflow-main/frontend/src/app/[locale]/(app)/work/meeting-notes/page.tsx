"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { BookOpen, Plus, X, Users, Check } from "lucide-react";
import { api } from "@/lib/api-client";

interface MeetingNote {
  id: string; title: string | null; content: string | null;
  customer_id: string | null; deal_id: string | null;
  meeting_date: string | null; attendees: string[]; action_items: { text: string; done: boolean }[];
  created_at: string | null;
}
interface Customer { id: string; name: string }

export default function MeetingNotesPage() {
  const [notes, setNotes] = useState<MeetingNote[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<MeetingNote | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", content: "", customer_id: "", meeting_date: new Date().toISOString().slice(0, 16), attendees: "" });

  async function load() {
    const [n, c] = await Promise.all([
      api.get<MeetingNote[]>("/api/work/meeting-notes").catch(() => [] as MeetingNote[]),
      api.get<Customer[]>("/api/invoicing/customers").catch(() => [] as Customer[]),
    ]);
    setNotes(n); setCustomers(c); setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function create() {
    if (!form.title.trim()) { toast.error("Title required"); return; }
    const body = {
      title: form.title, content: form.content, meeting_date: form.meeting_date,
      customer_id: form.customer_id || null,
      attendees: form.attendees ? form.attendees.split(",").map(s => s.trim()) : [],
    };
    try {
      await api.post<MeetingNote>("/api/work/meeting-notes", body);
      toast.success("Note saved"); setShowForm(false); setForm({ title: "", content: "", customer_id: "", meeting_date: new Date().toISOString().slice(0, 16), attendees: "" }); load();
    } catch { toast.error("Failed"); }
  }

  async function remove(id: string) {
    await api.delete(`/api/work/meeting-notes/${id}`);
    setNotes(prev => prev.filter(n => n.id !== id)); setSelected(null); toast.success("Deleted");
  }

  const custMap = Object.fromEntries(customers.map(c => [c.id, c.name]));

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Meeting Notes</h1>
          <p className="mt-1 text-sm text-gray-500">Log meetings tied to customers or deals with action items.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2"><Plus className="h-4 w-4" /> New Note</button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input col-span-full" placeholder="Meeting title" value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
            <select className="input" value={form.customer_id} onChange={e => setForm(p => ({ ...p, customer_id: e.target.value }))}>
              <option value="">No customer</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <input className="input" type="datetime-local" value={form.meeting_date} onChange={e => setForm(p => ({ ...p, meeting_date: e.target.value }))} />
            <input className="input col-span-full" placeholder="Attendees (comma-separated)" value={form.attendees} onChange={e => setForm(p => ({ ...p, attendees: e.target.value }))} />
            <textarea className="input col-span-full h-24 resize-none" placeholder="Notes…" value={form.content} onChange={e => setForm(p => ({ ...p, content: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="btn-primary text-sm">Save</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {notes.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <BookOpen className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p>No meeting notes yet.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-2">
          {notes.map(note => (
            <button key={note.id} onClick={() => setSelected(note)}
              className={`w-full text-left rounded-xl border p-4 transition-all ${selected?.id === note.id ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"}`}>
              <p className="font-medium text-gray-900">{note.title || "Untitled"}</p>
              <div className="flex gap-3 text-xs text-gray-500 mt-1">
                {note.customer_id && <span>{custMap[note.customer_id] || "Customer"}</span>}
                {note.meeting_date && <span>{new Date(note.meeting_date).toLocaleDateString("sv-SE")}</span>}
                {note.attendees.length > 0 && <span className="flex items-center gap-1"><Users className="h-3 w-3" />{note.attendees.length}</span>}
              </div>
            </button>
          ))}
        </div>

        {selected && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-3">
            <div className="flex justify-between items-start">
              <h2 className="font-semibold text-gray-900 text-lg">{selected.title || "Untitled"}</h2>
              <button onClick={() => remove(selected.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500"><X className="h-4 w-4" /></button>
            </div>
            {selected.content && <p className="text-sm text-gray-700 whitespace-pre-wrap">{selected.content}</p>}
            {selected.attendees.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-1">Attendees</p>
                <div className="flex gap-1 flex-wrap">{selected.attendees.map((a, i) => <span key={i} className="text-xs bg-gray-100 px-2 py-0.5 rounded">{a}</span>)}</div>
              </div>
            )}
            {selected.action_items.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-1">Action Items</p>
                {selected.action_items.map((ai, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <div className={`w-4 h-4 rounded flex items-center justify-center ${ai.done ? "bg-green-500" : "border border-gray-300"}`}>
                      {ai.done && <Check className="h-2.5 w-2.5 text-white" />}
                    </div>
                    <span className={ai.done ? "line-through text-gray-400" : ""}>{ai.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
