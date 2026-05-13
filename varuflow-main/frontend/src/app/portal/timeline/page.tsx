"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface TimelineEvent {
  id: string;
  event_type: string;
  title: string;
  description: string | null;
  occurred_at: string;
  invoice_id: string | null;
}

const EVENT_ICONS: Record<string, string> = {
  order_placed: "📦",
  confirmed: "✅",
  shipped: "🚚",
  delivered: "🏠",
  invoice_sent: "📄",
  payment_received: "💳",
};

export default function PortalTimelinePage() {
  const router = useRouter();
  const [events, setEvents] = useState<TimelineEvent[]>([]);

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }
    portalApi.get<TimelineEvent[]>("/api/portal/timeline").then(setEvents).catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Order Timeline</h1>
      {events.length === 0 && <p className="text-gray-500 text-sm">No events yet.</p>}
      <div className="relative border-l-2 border-gray-200 ml-4 space-y-6">
        {events.map(e => (
          <div key={e.id} className="relative pl-8">
            <div className="absolute -left-3 top-1 w-6 h-6 rounded-full bg-white border-2 border-blue-400 flex items-center justify-center text-xs">
              {EVENT_ICONS[e.event_type] || "•"}
            </div>
            <div className="bg-white border rounded p-3">
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm">{e.title}</span>
                <span className="text-xs text-gray-400">{new Date(e.occurred_at).toLocaleDateString()}</span>
              </div>
              {e.description && <p className="text-xs text-gray-600 mt-1">{e.description}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
