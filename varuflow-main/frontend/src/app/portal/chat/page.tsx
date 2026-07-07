"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface Message {
  id: string;
  sender_type: string;
  body: string;
  created_at: string;
}

export default function PortalChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = () => {
    portalApi.get<Message[]>("/api/portal/chat").then(setMessages).catch(() => {});
  };

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async () => {
    if (!input.trim()) return;
    await portalApi.post("/api/portal/chat", { body: input });
    setInput("");
    load();
    // The bot (if the org enabled it) replies via a background task —
    // pull once more before the next 5s poll tick so it appears fast.
    setTimeout(load, 2500);
  };

  return (
    <div className="flex flex-col h-[70vh]">
      <h1 className="text-xl font-bold mb-4">Chat with us</h1>
      <div className="flex-1 overflow-y-auto border rounded p-4 space-y-3 bg-white">
        {messages.map(m => (
          <div key={m.id} className={`flex ${m.sender_type === "customer" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${m.sender_type === "customer" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"}`}>
              {m.sender_type === "bot" && (
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--vf-brand-primary)" }}>
                  Assistant
                </div>
              )}
              {m.body}
              <div className={`text-xs mt-1 ${m.sender_type === "customer" ? "text-blue-200" : "text-gray-400"}`}>
                {new Date(m.created_at).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder="Type a message..."
          className="flex-1 border rounded px-3 py-2"
        />
        <button onClick={send} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Send</button>
      </div>
    </div>
  );
}
