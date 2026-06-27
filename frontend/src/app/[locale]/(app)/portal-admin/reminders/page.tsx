"use client";
import { useEffect, useState } from "react";

interface Reminder { id: string; invoice_id: string; customer_id: string; reminder_type: string; scheduled_for: string; sent_at: string | null; email_subject: string; }

export default function PortalAdminRemindersPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ invoice_id: "", customer_id: "", reminder_type: "gentle", scheduled_for: "", email_subject: "", email_body: "" });

  const load = () => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/portal-admin/reminders`, { credentials: "include" })
      .then(r => r.ok ? r.json() : []).then(setReminders);
  };

  useEffect(() => { load(); }, []);

  const create = async () => {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/portal-admin/reminders`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "include", body: JSON.stringify(form),
    });
    setShowCreate(false);
    setForm({ invoice_id: "", customer_id: "", reminder_type: "gentle", scheduled_for: "", email_subject: "", email_body: "" });
    load();
  };

  const typeBadge = (t: string) => {
    const colors: Record<string, string> = { gentle: "bg-green-100 text-green-800", followup: "bg-yellow-100 text-yellow-800", final: "bg-red-100 text-red-800" };
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[t] || "bg-gray-100"}`}>{t}</span>;
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Friendly Reminders</h1>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Schedule Reminder</button>
      </div>

      {showCreate && (
        <div className="border rounded p-4 space-y-2 bg-white">
          <input placeholder="Invoice ID" value={form.invoice_id} onChange={e => setForm({ ...form, invoice_id: e.target.value })} className="w-full border rounded px-3 py-2" />
          <input placeholder="Customer ID" value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value })} className="w-full border rounded px-3 py-2" />
          <select value={form.reminder_type} onChange={e => setForm({ ...form, reminder_type: e.target.value })} className="w-full border rounded px-3 py-2">
            <option value="gentle">Gentle</option>
            <option value="followup">Follow-up</option>
            <option value="final">Final</option>
          </select>
          <input type="datetime-local" value={form.scheduled_for} onChange={e => setForm({ ...form, scheduled_for: e.target.value })} className="w-full border rounded px-3 py-2" />
          <input placeholder="Email Subject" value={form.email_subject} onChange={e => setForm({ ...form, email_subject: e.target.value })} className="w-full border rounded px-3 py-2" />
          <textarea placeholder="Email Body" value={form.email_body} onChange={e => setForm({ ...form, email_body: e.target.value })} className="w-full border rounded px-3 py-2 h-24" />
          <div className="flex gap-2">
            <button onClick={create} className="px-4 py-2 bg-green-600 text-white rounded">Schedule</button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 bg-gray-200 rounded">Cancel</button>
          </div>
        </div>
      )}

      <table className="w-full text-sm border">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left">Subject</th>
            <th className="px-4 py-2 text-left">Type</th>
            <th className="px-4 py-2 text-left">Scheduled</th>
            <th className="px-4 py-2 text-left">Sent</th>
          </tr>
        </thead>
        <tbody>
          {reminders.map(r => (
            <tr key={r.id} className="border-t">
              <td className="px-4 py-2">{r.email_subject}</td>
              <td className="px-4 py-2">{typeBadge(r.reminder_type)}</td>
              <td className="px-4 py-2">{new Date(r.scheduled_for).toLocaleString()}</td>
              <td className="px-4 py-2">{r.sent_at ? new Date(r.sent_at).toLocaleString() : <span className="text-gray-400">Pending</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
