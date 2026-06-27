"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface Ticket {
  id: string;
  subject: string;
  status: string;
  priority: string;
  created_at: string;
}

export default function PortalTicketsPage() {
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ subject: "", description: "" });

  const load = () => {
    portalApi.get<Ticket[]>("/api/portal/tickets").then(setTickets).catch(() => {});
  };

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }
    load();
  }, []);

  const create = async () => {
    if (!form.subject.trim()) return;
    await portalApi.post("/api/portal/tickets", form);
    setShowCreate(false);
    setForm({ subject: "", description: "" });
    load();
  };

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = { open: "bg-yellow-100 text-yellow-800", in_progress: "bg-blue-100 text-blue-800", resolved: "bg-green-100 text-green-800", closed: "bg-gray-100 text-gray-800" };
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[s] || "bg-gray-100"}`}>{s}</span>;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Support Tickets</h1>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">New Ticket</button>
      </div>

      {showCreate && (
        <div className="border rounded p-4 space-y-2 bg-white">
          <input placeholder="Subject" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} className="w-full border rounded px-3 py-2" />
          <textarea placeholder="Describe your issue..." value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full border rounded px-3 py-2 h-24" />
          <div className="flex gap-2">
            <button onClick={create} className="px-4 py-2 bg-green-600 text-white rounded text-sm">Submit</button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 bg-gray-200 rounded text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {tickets.map(t => (
          <Link key={t.id} href={`/portal/tickets/${t.id}`} className="block border rounded p-3 bg-white hover:bg-gray-50">
            <div className="flex items-center justify-between">
              <span className="font-medium">{t.subject}</span>
              {statusBadge(t.status)}
            </div>
            <div className="text-xs text-gray-500 mt-1">{new Date(t.created_at).toLocaleDateString()}</div>
          </Link>
        ))}
        {tickets.length === 0 && <p className="text-gray-500 text-sm">No tickets yet.</p>}
      </div>
    </div>
  );
}
