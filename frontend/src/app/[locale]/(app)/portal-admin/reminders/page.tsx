"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface Reminder { id: string; invoice_id: string; customer_id: string; reminder_type: string; scheduled_for: string; sent_at: string | null; email_subject: string; }

export default function PortalAdminRemindersPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ invoice_id: "", customer_id: "", reminder_type: "gentle", scheduled_for: "", email_subject: "", email_body: "" });

  const load = () => {
    api.get<Reminder[]>("/api/portal-admin/reminders").then(setReminders).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  const create = async () => {
    try {
      await api.post("/api/portal-admin/reminders", form);
      setShowCreate(false);
      setForm({ invoice_id: "", customer_id: "", reminder_type: "gentle", scheduled_for: "", email_subject: "", email_body: "" });
      load();
    } catch { /* toast handled by api client */ }
  };

  const typeBadge = (t: string) => {
    const TYPE_MODULE: Record<string, keyof typeof styles> = {
      gentle:   "typeGentle",
      followup: "typeFollowup",
      final:    "typeFinal",
    };
    return <span className={styles[TYPE_MODULE[t] ?? "typeGentle"]}>{t}</span>;
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
