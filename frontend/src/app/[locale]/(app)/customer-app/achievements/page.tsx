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

interface Achievement {
  id: string;
  title: string;
  description: string;
  trigger_type: string;
  trigger_value: number;
  badge_color: string;
}

interface EarnedAchievement {
  id: string;
  achievement_id: string;
  title: string;
  badge_color: string;
  earned_at: string;
}

export default function AchievementsPage() {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newForm, setNewForm] = useState({ title: "", description: "", trigger_type: "visit_count", trigger_value: "", badge_color: "#FFD700" });
  const [creating, setCreating] = useState(false);

  const [awardCustomerId, setAwardCustomerId] = useState("");
  const [awardAchievementId, setAwardAchievementId] = useState("");
  const [awarding, setAwarding] = useState(false);
  const [awardError, setAwardError] = useState("");

  const [earnedCustomerId, setEarnedCustomerId] = useState("");
  const [earned, setEarned] = useState<EarnedAchievement[]>([]);
  const [earnedLoading, setEarnedLoading] = useState(false);
  const [earnedError, setEarnedError] = useState("");

  async function fetchAchievements() {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Achievement[]>("/api/achievements");
      setAchievements(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load achievements.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchAchievements(); }, []);

  async function createAchievement() {
    setCreating(true);
    setError("");
    try {
      await api.post("/api/achievements", { ...newForm, trigger_value: parseFloat(newForm.trigger_value) || 0 });
      setNewForm({ title: "", description: "", trigger_type: "visit_count", trigger_value: "", badge_color: "#FFD700" });
      fetchAchievements();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create achievement.");
    } finally {
      setCreating(false);
    }
  }

  async function deleteAchievement(id: string) {
    setError("");
    try {
      await api.delete(`/api/achievements/${id}`);
      setAchievements(achievements.filter((a) => a.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
    }
  }

  async function awardAchievement() {
    if (!awardCustomerId || !awardAchievementId) return;
    setAwarding(true);
    setAwardError("");
    try {
      await api.post("/api/achievements/award", { customer_id: awardCustomerId, achievement_id: awardAchievementId });
      setAwardCustomerId("");
      setAwardAchievementId("");
    } catch (e) {
      setAwardError(e instanceof Error ? e.message : "Failed to award achievement.");
    } finally {
      setAwarding(false);
    }
  }

  async function loadEarned() {
    if (!earnedCustomerId) return;
    setEarnedLoading(true);
    setEarnedError("");
    try {
      const data = await api.get<EarnedAchievement[]>(`/api/achievements/earned?customer_id=${earnedCustomerId}`);
      setEarned(data);
    } catch (e) {
      setEarnedError(e instanceof Error ? e.message : "Failed to load earned achievements.");
    } finally {
      setEarnedLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Achievements</h1>
      <p className="text-muted-foreground">Define achievement badges and view which customers earned them.</p>

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading && <p className="text-muted-foreground">Loading...</p>}

      <Card>
        <CardHeader><CardTitle>Achievement Definitions ({achievements.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Trigger Type</TableHead>
                <TableHead>Trigger Value</TableHead>
                <TableHead>Badge</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {achievements.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{a.title}</TableCell>
                  <TableCell>{a.trigger_type}</TableCell>
                  <TableCell>{a.trigger_value}</TableCell>
                  <TableCell>
                    <span
                      className="inline-block w-6 h-6 rounded-full border"
                      style={{ backgroundColor: a.badge_color }}
                    />
                  </TableCell>
                  <TableCell>
                    <Button size="sm" variant="destructive" onClick={() => deleteAchievement(a.id)}>Delete</Button>
                  </TableCell>
                </TableRow>
              ))}
              {achievements.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">No achievements defined.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Add Achievement</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Title" value={newForm.title} onChange={(e) => setNewForm({ ...newForm, title: e.target.value })} />
          <Input placeholder="Description" value={newForm.description} onChange={(e) => setNewForm({ ...newForm, description: e.target.value })} />
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-background"
            value={newForm.trigger_type}
            onChange={(e) => setNewForm({ ...newForm, trigger_type: e.target.value })}
          >
            <option value="visit_count">Visit Count</option>
            <option value="month_streak">Month Streak</option>
            <option value="spend_amount">Spend Amount</option>
            <option value="referrals">Referrals</option>
          </select>
          <Input type="number" placeholder="Trigger Value" value={newForm.trigger_value} onChange={(e) => setNewForm({ ...newForm, trigger_value: e.target.value })} />
          <div className="flex items-center gap-2">
            <label className="text-sm">Badge Color</label>
            <input type="color" value={newForm.badge_color} onChange={(e) => setNewForm({ ...newForm, badge_color: e.target.value })} className="h-8 w-16 cursor-pointer" />
          </div>
          <Button onClick={createAchievement} disabled={creating}>
            {creating ? "Creating..." : "Add Achievement"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Award Achievement</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Customer UUID" value={awardCustomerId} onChange={(e) => setAwardCustomerId(e.target.value)} />
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-background"
            value={awardAchievementId}
            onChange={(e) => setAwardAchievementId(e.target.value)}
          >
            <option value="">Select achievement...</option>
            {achievements.map((a) => (
              <option key={a.id} value={a.id}>{a.title}</option>
            ))}
          </select>
          {awardError && <p className="text-red-500 text-sm">{awardError}</p>}
          <Button onClick={awardAchievement} disabled={awarding || !awardCustomerId || !awardAchievementId}>
            {awarding ? "Awarding..." : "Award"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>View Earned Badges</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Customer UUID"
              value={earnedCustomerId}
              onChange={(e) => setEarnedCustomerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadEarned} disabled={earnedLoading}>
              {earnedLoading ? "Loading..." : "Load"}
            </Button>
          </div>
          {earnedError && <p className="text-red-500 text-sm">{earnedError}</p>}
          {earnedLoading && <p className="text-muted-foreground">Loading...</p>}
          <div className="flex flex-wrap gap-2">
            {earned.map((e) => (
              <Badge
                key={e.id}
                style={{ backgroundColor: e.badge_color, color: "#fff" }}
                className="text-xs"
              >
                {e.title} — {e.earned_at}
              </Badge>
            ))}
            {earned.length === 0 && !earnedLoading && earnedCustomerId && (
              <p className="text-muted-foreground text-sm">No badges earned.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
