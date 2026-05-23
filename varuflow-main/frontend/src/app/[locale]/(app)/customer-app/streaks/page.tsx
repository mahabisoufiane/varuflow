"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const API = process.env.NEXT_PUBLIC_API_URL;

interface Streak {
  streak_type: string;
  current_count: number;
  longest_count: number;
  last_activity_date: string | null;
  streak_start_date: string | null;
}

interface LeaderboardEntry {
  customer_id: string;
  current_count: number;
  longest_count: number;
}

export default function StreaksPage() {
  const { locale } = useParams<{ locale: string }>();
  const [customerId, setCustomerId] = useState("");
  const [streaks, setStreaks] = useState<Streak[]>([]);
  const [streakLoading, setStreakLoading] = useState(false);
  const [streakError, setStreakError] = useState("");

  const [editingType, setEditingType] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ current_count: "", longest_count: "", last_activity_date: "" });
  const [updating, setUpdating] = useState(false);

  const [leaderboardType, setLeaderboardType] = useState("monthly_visit");
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [lbLoading, setLbLoading] = useState(false);
  const [lbError, setLbError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function loadStreaks() {
    if (!customerId.trim()) return;
    setStreakLoading(true);
    setStreakError("");
    try {
      const res = await fetch(`${API}/api/streaks?customer_id=${customerId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setStreakError("Unauthorized."); return; }
      if (!res.ok) { setStreakError("Failed to load streaks."); return; }
      setStreaks(await res.json());
    } catch {
      setStreakError("Network error.");
    } finally {
      setStreakLoading(false);
    }
  }

  async function updateStreak(streakType: string) {
    setUpdating(true);
    setStreakError("");
    try {
      const res = await fetch(`${API}/api/streaks/${customerId}/${streakType}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          current_count: parseInt(editForm.current_count) || 0,
          longest_count: parseInt(editForm.longest_count) || 0,
          last_activity_date: editForm.last_activity_date || null,
        }),
      });
      if (!res.ok) { setStreakError("Update failed."); return; }
      setEditingType(null);
      loadStreaks();
    } catch {
      setStreakError("Network error.");
    } finally {
      setUpdating(false);
    }
  }

  async function loadLeaderboard() {
    setLbLoading(true);
    setLbError("");
    try {
      const res = await fetch(`${API}/api/streaks/leaderboard?streak_type=${leaderboardType}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setLbError("Unauthorized."); return; }
      if (!res.ok) { setLbError("Failed to load leaderboard."); return; }
      setLeaderboard(await res.json());
    } catch {
      setLbError("Network error.");
    } finally {
      setLbLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Loyalty Streaks</h1>
      <p className="text-muted-foreground">View and manage customer visit streaks.</p>

      <Card>
        <CardHeader><CardTitle>Customer Streak Lookup</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Customer UUID"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadStreaks} disabled={streakLoading}>
              {streakLoading ? "Loading..." : "Load"}
            </Button>
          </div>
          {streakError && <p className="text-red-500 text-sm">{streakError}</p>}
          {streakLoading && <p className="text-muted-foreground">Loading...</p>}

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {streaks.map((streak) => (
              <Card key={streak.streak_type}>
                <CardHeader>
                  <CardTitle className="text-base capitalize">{streak.streak_type.replace(/_/g, " ")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {editingType === streak.streak_type ? (
                    <div className="space-y-2">
                      <Input
                        type="number"
                        placeholder="Current Count"
                        value={editForm.current_count}
                        onChange={(e) => setEditForm({ ...editForm, current_count: e.target.value })}
                      />
                      <Input
                        type="number"
                        placeholder="Longest Count"
                        value={editForm.longest_count}
                        onChange={(e) => setEditForm({ ...editForm, longest_count: e.target.value })}
                      />
                      <div>
                        <label className="text-xs text-muted-foreground">Last Activity Date</label>
                        <Input
                          type="date"
                          value={editForm.last_activity_date}
                          onChange={(e) => setEditForm({ ...editForm, last_activity_date: e.target.value })}
                        />
                      </div>
                      <div className="flex gap-1">
                        <Button size="sm" onClick={() => updateStreak(streak.streak_type)} disabled={updating}>
                          {updating ? "Saving..." : "Save"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingType(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="text-sm">Current: <strong>{streak.current_count}</strong></p>
                      <p className="text-sm">Longest: <strong>{streak.longest_count}</strong></p>
                      <p className="text-xs text-muted-foreground">Last Activity: {streak.last_activity_date ?? "—"}</p>
                      <p className="text-xs text-muted-foreground">Started: {streak.streak_start_date ?? "—"}</p>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingType(streak.streak_type);
                          setEditForm({
                            current_count: String(streak.current_count),
                            longest_count: String(streak.longest_count),
                            last_activity_date: streak.last_activity_date ?? "",
                          });
                        }}
                      >
                        Update Streak
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            ))}
            {streaks.length === 0 && !streakLoading && customerId && (
              <p className="text-muted-foreground text-sm col-span-full">No streaks found.</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Leaderboard</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <select
              className="border rounded px-3 py-2 text-sm bg-background"
              value={leaderboardType}
              onChange={(e) => setLeaderboardType(e.target.value)}
            >
              <option value="monthly_visit">Monthly Visit</option>
              <option value="weekly_visit">Weekly Visit</option>
            </select>
            <Button onClick={loadLeaderboard} disabled={lbLoading}>
              {lbLoading ? "Loading..." : "Load Leaderboard"}
            </Button>
          </div>
          {lbError && <p className="text-red-500 text-sm">{lbError}</p>}
          {lbLoading && <p className="text-muted-foreground">Loading...</p>}
          {leaderboard.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>Customer ID</TableHead>
                  <TableHead>Current Count</TableHead>
                  <TableHead>Longest Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leaderboard.map((entry, idx) => (
                  <TableRow key={entry.customer_id}>
                    <TableCell className="font-bold">{idx + 1}</TableCell>
                    <TableCell className="font-mono text-xs">{entry.customer_id}</TableCell>
                    <TableCell>{entry.current_count}</TableCell>
                    <TableCell>{entry.longest_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
