"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";
import { FileX } from "lucide-react";

interface CreditNote {
  id: string;
  number: string | null;
  status: string;
  total: string | null;
  created_at: string | null;
}

export default function PortalCreditNotesPage() {
  const router = useRouter();
  const [notes, setNotes] = useState<CreditNote[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<CreditNote[]>("/api/portal/credit-notes")
      .then(setNotes)
      .catch(() => toast.error("Failed to load credit notes"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <FileX size={20} /> Credit Notes
      </h1>

      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : notes.length === 0 ? (
        <p className="text-center text-sm text-gray-500 py-8">No credit notes on your account.</p>
      ) : (
        <div className="space-y-2">
          {notes.map(n => (
            <div key={n.id} className="bg-white border rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{n.number || `CN-${n.id.slice(0, 8)}`}</p>
                <p className="text-xs text-gray-400">
                  {n.created_at ? new Date(n.created_at).toLocaleDateString() : "—"}
                </p>
              </div>
              <div className="text-right">
                {n.total && (
                  <p className="font-semibold text-sm">{n.total} SEK</p>
                )}
                <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-800">{n.status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
