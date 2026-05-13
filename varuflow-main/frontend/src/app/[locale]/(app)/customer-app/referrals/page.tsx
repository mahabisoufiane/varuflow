"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const API = process.env.NEXT_PUBLIC_API_URL;

type ReferralStatus = "pending" | "qualified" | "rewarded";

interface Referral {
  id: string;
  referral_code: string;
  referrer_customer_id: string;
  referred_customer_id: string | null;
  status: ReferralStatus;
  reward_points: number | null;
  qualified_at: string | null;
  created_at: string;
}

const STATUS_TABS: Array<{ label: string; value: string }> = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Qualified", value: "qualified" },
  { label: "Rewarded", value: "rewarded" },
];

export default function ReferralsPage() {
  const { locale } = useParams<{ locale: string }>();
  const [items, setItems] = useState<Referral[]>([]);
  const [filterReferrerId, setFilterReferrerId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newReferrerId, setNewReferrerId] = useState("");
  const [creating, setCreating] = useState(false);
  const [rewardPointsMap, setRewardPointsMap] = useState<Record<string, string>>({});

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterReferrerId) params.set("referrer_customer_id", filterReferrerId);
      if (statusFilter) params.set("status", statusFilter);
      const res = await fetch(`${API}/api/loyalty-referrals?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to load referrals."); return; }
      setItems(await res.json());
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, [statusFilter]);

  async function qualify(id: string) {
    setError("");
    try {
      const res = await fetch(`${API}/api/loyalty-referrals/${id}/qualify`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("Qualify failed."); return; }
      fetchItems();
    } catch {
      setError("Network error.");
    }
  }

  async function reward(id: string) {
    const pts = parseInt(rewardPointsMap[id] || "0");
    setError("");
    try {
      const res = await fetch(`${API}/api/loyalty-referrals/${id}/reward`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ reward_points: pts }),
      });
      if (!res.ok) { setError("Reward failed."); return; }
      fetchItems();
    } catch {
      setError("Network error.");
    }
  }

  async function createReferral() {
    if (!newReferrerId.trim()) return;
    setCreating(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/loyalty-referrals`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ referrer_customer_id: newReferrerId }),
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to create referral."); return; }
      setNewReferrerId("");
      fetchItems();
    } catch {
      setError("Network error.");
    } finally {
      setCreating(false);
    }
  }

  const statusVariant = (s: string) => {
    if (s === "rewarded") return "default";
    if (s === "qualified") return "secondary";
    return "outline";
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Referral Tracking</h1>
      <p className="text-muted-foreground">Track refer-a-friend campaigns and reward referrers.</p>

      <Card>
        <CardHeader><CardTitle>Filter</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Referrer Customer ID (optional)"
              value={filterReferrerId}
              onChange={(e) => setFilterReferrerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={fetchItems} disabled={loading}>
              {loading ? "Loading..." : "Search"}
            </Button>
          </div>
          <div className="flex gap-2">
            {STATUS_TABS.map((tab) => (
              <Button
                key={tab.value}
                size="sm"
                variant={statusFilter === tab.value ? "default" : "outline"}
                onClick={() => setStatusFilter(tab.value)}
              >
                {tab.label}
              </Button>
            ))}
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {loading && <p className="text-muted-foreground">Loading...</p>}

      <Card>
        <CardHeader><CardTitle>Referrals ({items.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Referrer ID</TableHead>
                <TableHead>Referred ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Reward Pts</TableHead>
                <TableHead>Qualified At</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono font-bold">{item.referral_code}</TableCell>
                  <TableCell className="font-mono text-xs">{item.referrer_customer_id}</TableCell>
                  <TableCell className="font-mono text-xs">{item.referred_customer_id ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.reward_points ?? "—"}</TableCell>
                  <TableCell>{item.qualified_at ?? "—"}</TableCell>
                  <TableCell>
                    <div className="flex gap-1 flex-wrap items-center">
                      {item.status === "pending" && (
                        <Button size="sm" variant="outline" onClick={() => qualify(item.id)}>Qualify</Button>
                      )}
                      {item.status === "qualified" && (
                        <div className="flex gap-1 items-center">
                          <Input
                            type="number"
                            placeholder="Points"
                            className="w-20 h-7 text-xs"
                            value={rewardPointsMap[item.id] ?? ""}
                            onChange={(e) => setRewardPointsMap({ ...rewardPointsMap, [item.id]: e.target.value })}
                          />
                          <Button size="sm" variant="outline" onClick={() => reward(item.id)}>Reward</Button>
                        </div>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">No referrals found.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>New Referral</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">Referral code is auto-generated.</p>
          <div className="flex gap-2">
            <Input
              placeholder="Referrer Customer ID"
              value={newReferrerId}
              onChange={(e) => setNewReferrerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={createReferral} disabled={creating}>
              {creating ? "Creating..." : "Create Referral"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
