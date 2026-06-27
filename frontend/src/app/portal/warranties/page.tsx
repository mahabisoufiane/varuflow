"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface Warranty {
  id: string;
  product_name_snapshot: string | null;
  serial_number: string | null;
  warranty_months: number;
  starts_at: string;
  expires_at: string;
  status: string;
}

export default function PortalWarrantiesPage() {
  const router = useRouter();
  const [warranties, setWarranties] = useState<Warranty[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<Warranty[]>("/api/portal/warranties").then(setWarranties).finally(() => setLoading(false));
  }, []);

  const today = new Date().toISOString().slice(0, 10);

  const badge = (w: Warranty) => {
    if (w.status === "expired" || w.expires_at < today) return <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700">Expired</span>;
    const daysLeft = Math.ceil((new Date(w.expires_at).getTime() - Date.now()) / 86400000);
    if (daysLeft <= 30) return <span className="px-2 py-0.5 rounded text-xs bg-yellow-100 text-yellow-700">Expiring soon ({daysLeft}d)</span>;
    return <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-800">Active</span>;
  };

  if (loading) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Warranties</h1>
      {warranties.length === 0 && <p className="text-sm text-gray-500">No warranties on file.</p>}
      <div className="space-y-2">
        {warranties.map(w => (
          <div key={w.id} className="border rounded p-3 bg-white">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium text-sm">{w.product_name_snapshot || "Product"}</p>
                {w.serial_number && <p className="text-xs text-gray-500">S/N: {w.serial_number}</p>}
              </div>
              {badge(w)}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {w.warranty_months} months · {w.starts_at} → {w.expires_at}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
