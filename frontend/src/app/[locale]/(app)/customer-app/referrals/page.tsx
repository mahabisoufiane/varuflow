"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

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
  const [items, setItems] = useState<Referral[]>([]);
  const [filterReferrerId, setFilterReferrerId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newReferrerId, setNewReferrerId] = useState("");
  const [creating, setCreating] = useState(false);
  const [rewardPointsMap, setRewardPointsMap] = useState<Record<string, string>>({});

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterReferrerId) params.set("referrer_customer_id", filterReferrerId);
      if (statusFilter) params.set("status", statusFilter);
      const data = await api.get<Referral[]>(`/api/loyalty-referrals?${params}`);
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load referrals.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, [statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  async function qualify(id: string) {
    setError("");
    try {
      await api.post(`/api/loyalty-referrals/${id}/qualify`, {});
      fetchItems();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Qualify failed.");
    }
  }

  async function reward(id: string) {
    const pts = parseInt(rewardPointsMap[id] || "0");
    setError("");
    try {
      await api.post(`/api/loyalty-referrals/${id}/reward`, { reward_points: pts });
      fetchItems();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reward failed.");
    }
  }

  async function createReferral() {
    if (!newReferrerId.trim()) return;
    setCreating(true);
    setError("");
    try {
      await api.post("/api/loyalty-referrals", { referrer_customer_id: newReferrerId });
      setNewReferrerId("");
      fetchItems();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create referral.");
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
