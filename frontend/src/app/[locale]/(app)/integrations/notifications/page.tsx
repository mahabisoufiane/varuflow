"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Bell, Trash2, TestTube } from "lucide-react";
import { api } from "@/lib/api-client";

const ALL_EVENTS = [
  { key: "stock.low", label: "Low stock alert" },
  { key: "invoice.overdue", label: "Invoice overdue" },
  { key: "new_po", label: "New purchase order" },
  { key: "payment_received", label: "Payment received" },
  { key: "customer.created", label: "New customer" },
  { key: "invoice.created", label: "Invoice created" },
  { key: "invoice.paid", label: "Invoice paid" },
];

interface Channel {
  id: string;
  channel_type: string;
  name: string;
  webhook_url: string;
  events: string[];
  is_active: boolean;
  last_sent_at?: string;
}

export default function NotificationsIntegrationPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [form, setForm] = useState({ channel_type: "slack", name: "", webhook_url: "", events: [] as string[] });

  async function load() {
    try {
      const data = await api.get<{ channels?: Channel[] }>("/api/integrations/notifications/channels");
      setChannels(data.channels ?? []);
    } catch {}
  }

  useEffect(() => { load(); }, []);

  async function createChannel() {
    if (!form.name || !form.webhook_url) { toast.error("Name and webhook URL are required"); return; }
    try {
      await api.post("/api/integrations/notifications/channels", form);
      toast.success("Channel added");
      setShowForm(false);
      setForm({ channel_type: "slack", name: "", webhook_url: "", events: [] });
      await load();
    } catch (err: any) {
      toast.error(err.message || "Failed to add channel");
    }
  }

  async function deleteChannel(id: string) {
    try {
      await api.delete(`/api/integrations/notifications/channels/${id}`);
      toast.success("Channel removed");
      await load();
    } catch {}
  }

  async function testChannel(id: string) {
    setTesting(id);
    try {
      await api.post(`/api/integrations/notifications/channels/${id}/test`, {});
      toast.success("Test notification sent");
    } catch {
      toast.error("Test failed — check your webhook URL");
    }
    setTesting(null);
  }

  function toggleEvent(key: string) {
    setForm(f => ({
      ...f,
      events: f.events.includes(key) ? f.events.filter(e => e !== key) : [...f.events, key],
    }));
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Notification Channels</h1>
          <p className="mt-1 text-sm text-gray-500">Send Varuflow events to Slack or Microsoft Teams.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary">+ Add Channel</button>
      </div>

      {/* Channel list */}
      {channels.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
          No channels configured yet. Add your first Slack or Teams webhook.
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map(ch => (
            <div key={ch.id} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Bell className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="font-medium text-sm text-gray-900">{ch.name}</p>
                    <p className="text-xs text-gray-500 capitalize">{ch.channel_type} · {ch.events.length} event{ch.events.length !== 1 ? "s" : ""}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => testChannel(ch.id)} disabled={testing === ch.id} className="btn-sm-outline">
                    <TestTube className="h-3.5 w-3.5 mr-1" />{testing === ch.id ? "Sending…" : "Test"}
                  </button>
                  <button onClick={() => deleteChannel(ch.id)} className="btn-sm-danger-outline">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              {ch.events.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {ch.events.map(e => (
                    <span key={e} className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">{e}</span>
                  ))}
                </div>
              )}
              {ch.last_sent_at && (
                <p className="mt-1 text-xs text-gray-400">Last sent: {new Date(ch.last_sent_at).toLocaleString()}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add channel slide-over / modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 space-y-4 shadow-xl">
            <h2 className="text-lg font-semibold">Add Notification Channel</h2>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Channel Type</label>
              <select className="input w-full" value={form.channel_type} onChange={e => setForm(f => ({ ...f, channel_type: e.target.value }))}>
                <option value="slack">Slack</option>
                <option value="teams">Microsoft Teams</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
              <input className="input w-full" placeholder="#general-alerts" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Webhook URL</label>
              <input className="input w-full" placeholder="https://hooks.slack.com/..." value={form.webhook_url} onChange={e => setForm(f => ({ ...f, webhook_url: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-2">Events to receive</label>
              <div className="grid grid-cols-2 gap-2">
                {ALL_EVENTS.map(ev => (
                  <label key={ev.key} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={form.events.includes(ev.key)} onChange={() => toggleEvent(ev.key)} className="rounded" />
                    {ev.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={createChannel} className="btn-primary flex-1">Save Channel</button>
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
