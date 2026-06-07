"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

interface UnreadCustomer { customer_id: string; unread_count: number; last_message_at: string | null; }
interface Message { id: string; sender_type: string; body: string; created_at: string; }

export default function PortalAdminChatPage() {
  const [customers, setCustomers] = useState<UnreadCustomer[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    api.get<UnreadCustomer[]>("/api/portal-admin/chat/unread").then(setCustomers).catch(() => {});
  }, []);

  const openChat = async (customerId: string) => {
    setSelected(customerId);
    api.get<Message[]>(`/api/portal-admin/chat/${customerId}`).then(setMessages).catch(() => {});
  };

  const send = async () => {
    if (!input.trim() || !selected) return;
    await api.post(`/api/portal-admin/chat/${selected}`, { body: input });
    setInput("");
    openChat(selected);
  };

  return (
    <div className="p-6 flex gap-4 h-[80vh]">
      <div className="w-64 border rounded overflow-y-auto bg-white">
        <h2 className="p-3 font-bold border-b">Conversations</h2>
        {customers.map(c => (
          <button key={c.customer_id} onClick={() => openChat(c.customer_id)} className={`w-full text-left px-3 py-2 border-b hover:bg-gray-50 ${selected === c.customer_id ? "bg-blue-50" : ""}`}>
            <div className="text-sm font-medium truncate">{c.customer_id.slice(0, 8)}...</div>
            <div className="text-xs text-gray-500 flex justify-between">
              <span>{c.unread_count} unread</span>
              <span>{c.last_message_at ? new Date(c.last_message_at).toLocaleDateString() : ""}</span>
            </div>
          </button>
        ))}
        {customers.length === 0 && <p className="p-3 text-sm text-gray-500">No unread messages</p>}
      </div>
      <div className="flex-1 flex flex-col border rounded bg-white">
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {messages.map(m => (
            <div key={m.id} className={`flex ${m.sender_type === "staff" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${m.sender_type === "staff" ? "bg-blue-600 text-white" : "bg-gray-100"}`}>
                {m.body}
                <div className={`text-xs mt-1 ${m.sender_type === "staff" ? "text-blue-200" : "text-gray-400"}`}>{new Date(m.created_at).toLocaleTimeString()}</div>
              </div>
            </div>
          ))}
        </div>
        {selected && (
          <div className="p-3 border-t flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder="Reply..." className="flex-1 border rounded px-3 py-2" />
            <button onClick={send} className="px-4 py-2 bg-blue-600 text-white rounded">Send</button>
          </div>
        )}
      </div>
    </div>
  );
}
