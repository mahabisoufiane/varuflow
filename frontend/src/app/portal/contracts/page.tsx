"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface NdaSummary { id: string; title: string; status: string; signed_at: string | null; created_at: string; }

export default function PortalContractsPage() {
  const router = useRouter();
  const [ndas, setNdas] = useState<NdaSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<NdaSummary[]>("/api/portal/contracts")
      .then(setNdas)
      .finally(() => setLoading(false));
  }, []);

  const badge = (s: string) => {
    const c: Record<string, string> = { pending: "bg-yellow-100 text-yellow-800", signed: "bg-green-100 text-green-800" };
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${c[s] || "bg-gray-100"}`}>{s}</span>;
  };

  if (loading) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Contracts & NDAs</h1>
      {ndas.length === 0 && <p className="text-sm text-gray-500">No contracts to review.</p>}
      <div className="space-y-2">
        {ndas.map(n => (
          <Link key={n.id} href={`/portal/contracts/${n.id}`} className="block bg-white border rounded p-3 hover:bg-gray-50">
            <div className="flex justify-between items-center">
              <span className="font-medium">{n.title}</span>
              {badge(n.status)}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {n.signed_at ? `Signed ${new Date(n.signed_at).toLocaleDateString()}` : `Sent ${new Date(n.created_at).toLocaleDateString()}`}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
