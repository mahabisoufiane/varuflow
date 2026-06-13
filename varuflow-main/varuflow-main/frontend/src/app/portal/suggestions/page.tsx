"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";

interface Suggestion {
  id: string;
  trigger_type: string;
  product_ids: string | null;
  message: string | null;
  shown_at: string | null;
}

export default function PortalSuggestionsPage() {
  const router = useRouter();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  const load = () => {
    portalApi.get<Suggestion[]>("/api/portal/suggestions").then(setSuggestions).catch(() => {});
  };

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    load();
  }, []);

  const dismiss = async (id: string) => {
    try {
      await portalApi.post(`/api/portal/suggestions/${id}/dismiss`, {});
      setSuggestions(s => s.filter(x => x.id !== id));
    } catch {
      toast.error("Failed to dismiss");
    }
  };

  const click = async (id: string) => {
    await portalApi.post(`/api/portal/suggestions/${id}/click`, {}).catch(() => {});
  };

  if (suggestions.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">Recommendations</h1>
        <p className="text-sm text-gray-500">No recommendations right now. Check back after your next purchase.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Recommendations for You</h1>
      <div className="space-y-3">
        {suggestions.map(s => (
          <div key={s.id} className="border rounded p-4 bg-white space-y-2">
            {s.message && <p className="text-sm">{s.message}</p>}
            {s.product_ids && (
              <p className="text-xs text-gray-500">Products: {s.product_ids}</p>
            )}
            <div className="flex gap-3 pt-1">
              <button
                onClick={() => click(s.id)}
                className="text-sm px-3 py-1.5 bg-[#1a2332] text-white rounded hover:opacity-90"
              >
                Learn More
              </button>
              <button
                onClick={() => dismiss(s.id)}
                className="text-sm text-gray-400 hover:text-gray-600"
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
