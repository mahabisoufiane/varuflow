"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface LoyaltyData { points_balance: number; lifetime_points: number; tier: string; transactions: { id: string; points: number; type: string; reason: string | null; created_at: string; }[]; }

export default function PortalLoyaltyPage() {
  const router = useRouter();
  const [data, setData] = useState<LoyaltyData | null>(null);
  const [redeemPts, setRedeemPts] = useState("");

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<LoyaltyData>("/api/portal/loyalty").then(setData);
  }, []);

  const redeem = async () => {
    const pts = parseInt(redeemPts);
    if (!pts || pts <= 0) return;
    await portalApi.post("/api/portal/loyalty/redeem", { points: pts });
    setRedeemPts("");
    portalApi.get<LoyaltyData>("/api/portal/loyalty").then(setData);
  };

  if (!data) return <div className="p-4">Loading...</div>;

  const tierColors: Record<string, string> = { bronze: "bg-orange-100 text-orange-800", silver: "bg-gray-100 text-gray-800", gold: "bg-yellow-100 text-yellow-800", platinum: "bg-purple-100 text-purple-800" };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Loyalty Points</h1>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border rounded p-4 text-center">
          <div className="text-sm text-gray-500">Balance</div>
          <div className="text-2xl font-bold">{data.points_balance}</div>
        </div>
        <div className="bg-white border rounded p-4 text-center">
          <div className="text-sm text-gray-500">Lifetime</div>
          <div className="text-xl">{data.lifetime_points}</div>
        </div>
        <div className="bg-white border rounded p-4 text-center">
          <div className="text-sm text-gray-500">Tier</div>
          <span className={`px-2 py-1 rounded text-sm font-medium ${tierColors[data.tier] || ""}`}>{data.tier}</span>
        </div>
      </div>
      <div className="flex gap-2">
        <input type="number" placeholder="Points to redeem" value={redeemPts} onChange={e => setRedeemPts(e.target.value)} className="border rounded px-3 py-2" />
        <button onClick={redeem} className="px-4 py-2 bg-blue-600 text-white rounded">Redeem</button>
      </div>
      <h2 className="font-bold mt-4">Recent Activity</h2>
      <div className="space-y-2">
        {data.transactions.map(t => (
          <div key={t.id} className="flex justify-between bg-white border rounded p-3 text-sm">
            <div><span className={t.points > 0 ? "text-green-600" : "text-red-600"}>{t.points > 0 ? "+" : ""}{t.points}</span> — {t.reason || t.type}</div>
            <span className="text-gray-400">{new Date(t.created_at).toLocaleDateString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
