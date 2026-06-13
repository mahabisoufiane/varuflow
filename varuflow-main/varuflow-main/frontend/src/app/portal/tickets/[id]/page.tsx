"use client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface Reply { id: string; sender_type: string; body: string; created_at: string; }
interface TicketDetail { id: string; subject: string; description: string | null; status: string; priority: string; created_at: string; replies: Reply[]; }

export default function PortalTicketDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [reply, setReply] = useState("");

  const load = () => {
    portalApi.get<TicketDetail>(`/api/portal/tickets/${params.id}`).then(setTicket).catch(() => {});
  };

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }
    load();
  }, [params.id]);

  const sendReply = async () => {
    if (!reply.trim()) return;
    await portalApi.post(`/api/portal/tickets/${params.id}/reply`, { body: reply });
    setReply("");
    load();
  };

  if (!ticket) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{ticket.subject}</h1>
      <div className="flex gap-2 text-sm">
        <span className="px-2 py-0.5 rounded bg-gray-100">{ticket.status}</span>
        <span className="text-gray-500">{new Date(ticket.created_at).toLocaleDateString()}</span>
      </div>
      {ticket.description && <p className="text-gray-700 bg-white border rounded p-3">{ticket.description}</p>}

      <div className="space-y-3">
        {ticket.replies.map(r => (
          <div key={r.id} className={`rounded p-3 text-sm ${r.sender_type === "customer" ? "bg-blue-50 ml-8" : "bg-gray-50 mr-8"}`}>
            <div className="font-medium text-xs text-gray-500 mb-1">{r.sender_type === "customer" ? "You" : "Support"} · {new Date(r.created_at).toLocaleString()}</div>
            <p>{r.body}</p>
          </div>
        ))}
      </div>

      {ticket.status !== "closed" && (
        <div className="flex gap-2">
          <input value={reply} onChange={e => setReply(e.target.value)} onKeyDown={e => e.key === "Enter" && sendReply()} placeholder="Write a reply..." className="flex-1 border rounded px-3 py-2" />
          <button onClick={sendReply} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Reply</button>
        </div>
      )}
    </div>
  );
}
