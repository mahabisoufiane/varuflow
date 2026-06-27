"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface MembershipTier {
  id: string;
  name: string;
  min_points: number;
  card_color: string;
  card_text_color: string;
  benefits: string;
}

interface CustomerMembership {
  customer_id: string;
  tier_id: string;
  tier_name: string;
}

export default function MembershipTiersPage() {
  const [tiers, setTiers] = useState<MembershipTier[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newTier, setNewTier] = useState({ name: "", min_points: "", card_color: "#C0A060", card_text_color: "#FFFFFF", benefits: "" });
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<MembershipTier>>({});

  const [assignCustomerId, setAssignCustomerId] = useState("");
  const [currentMembership, setCurrentMembership] = useState<CustomerMembership | null>(null);
  const [selectedTierId, setSelectedTierId] = useState("");
  const [membershipLoading, setMembershipLoading] = useState(false);
  const [membershipError, setMembershipError] = useState("");
  const [assigning, setAssigning] = useState(false);

  async function fetchTiers() {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<MembershipTier[]>("/api/membership-tiers");
      setTiers(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tiers.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchTiers(); }, []);

  async function createTier() {
    setCreating(true);
    setError("");
    try {
      await api.post("/api/membership-tiers", { ...newTier, min_points: parseInt(newTier.min_points) || 0 });
      setNewTier({ name: "", min_points: "", card_color: "#C0A060", card_text_color: "#FFFFFF", benefits: "" });
      fetchTiers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create tier.");
    } finally {
      setCreating(false);
    }
  }

  async function updateTier(id: string) {
    setError("");
    try {
      await api.put(`/api/membership-tiers/${id}`, editForm);
      setEditingId(null);
      fetchTiers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update tier.");
    }
  }

  async function deleteTier(id: string) {
    setError("");
    try {
      await api.delete(`/api/membership-tiers/${id}`);
      setTiers(tiers.filter((t) => t.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
    }
  }

  async function loadMembership() {
    if (!assignCustomerId.trim()) return;
    setMembershipLoading(true);
    setMembershipError("");
    try {
      const data = await api.get<CustomerMembership>(`/api/membership-tiers/memberships?customer_id=${assignCustomerId}`);
      setCurrentMembership(data);
      setSelectedTierId(data.tier_id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg.includes("404")) {
        setCurrentMembership(null);
      } else {
        setMembershipError(msg || "Failed to load membership.");
      }
    } finally {
      setMembershipLoading(false);
    }
  }

  async function assignTier() {
    if (!assignCustomerId.trim() || !selectedTierId) return;
    setAssigning(true);
    setMembershipError("");
    try {
      await api.put(`/api/membership-tiers/memberships/${assignCustomerId}`, { tier_id: selectedTierId });
      loadMembership();
    } catch (e) {
      setMembershipError(e instanceof Error ? e.message : "Failed to assign tier.");
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Membership Tiers</h1>
      <p className="text-muted-foreground">Configure Bronze/Silver/Gold/Platinum tier definitions and assign customers.</p>

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading && <p className="text-muted-foreground">Loading...</p>}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {tiers.map((tier) => (
          <Card key={tier.id}>
            <CardHeader>
              <div
                className="rounded-lg p-3 mb-2"
                style={{ backgroundColor: tier.card_color, color: tier.card_text_color }}
              >
                <span className="font-bold text-lg">{tier.name}</span>
              </div>
              <CardTitle className="text-base">{tier.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {editingId === tier.id ? (
                <div className="space-y-2">
                  <Input placeholder="Name" value={editForm.name ?? ""} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                  <Input type="number" placeholder="Min Points" value={editForm.min_points ?? ""} onChange={(e) => setEditForm({ ...editForm, min_points: parseInt(e.target.value) })} />
                  <Input type="color" value={editForm.card_color ?? "#C0A060"} onChange={(e) => setEditForm({ ...editForm, card_color: e.target.value })} />
                  <Input type="color" value={editForm.card_text_color ?? "#FFFFFF"} onChange={(e) => setEditForm({ ...editForm, card_text_color: e.target.value })} />
                  <Input placeholder="Benefits" value={editForm.benefits ?? ""} onChange={(e) => setEditForm({ ...editForm, benefits: e.target.value })} />
                  <div className="flex gap-1">
                    <Button size="sm" onClick={() => updateTier(tier.id)}>Save</Button>
                    <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-sm">Min Points: <strong>{tier.min_points}</strong></p>
                  <p className="text-sm">{tier.benefits}</p>
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" onClick={() => { setEditingId(tier.id); setEditForm(tier); }}>Edit</Button>
                    <Button size="sm" variant="destructive" onClick={() => deleteTier(tier.id)}>Delete</Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>Add Tier</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Name (e.g. Bronze)" value={newTier.name} onChange={(e) => setNewTier({ ...newTier, name: e.target.value })} />
          <Input type="number" placeholder="Min Points" value={newTier.min_points} onChange={(e) => setNewTier({ ...newTier, min_points: e.target.value })} />
          <div className="flex gap-4 items-center">
            <label className="text-sm">Card Color</label>
            <input type="color" value={newTier.card_color} onChange={(e) => setNewTier({ ...newTier, card_color: e.target.value })} className="h-8 w-16 cursor-pointer" />
            <label className="text-sm">Text Color</label>
            <input type="color" value={newTier.card_text_color} onChange={(e) => setNewTier({ ...newTier, card_text_color: e.target.value })} className="h-8 w-16 cursor-pointer" />
          </div>
          <Input placeholder="Benefits (comma-separated)" value={newTier.benefits} onChange={(e) => setNewTier({ ...newTier, benefits: e.target.value })} />
          <Button onClick={createTier} disabled={creating}>
            {creating ? "Creating..." : "Add Tier"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Assign Customer Tier</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Customer UUID"
              value={assignCustomerId}
              onChange={(e) => setAssignCustomerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadMembership} disabled={membershipLoading}>
              {membershipLoading ? "Loading..." : "Load"}
            </Button>
          </div>
          {membershipError && <p className="text-red-500 text-sm">{membershipError}</p>}
          {currentMembership && (
            <p className="text-sm">Current Tier: <Badge>{currentMembership.tier_name}</Badge></p>
          )}
          {assignCustomerId && (
            <div className="flex gap-2">
              <select
                className="border rounded px-3 py-2 text-sm bg-background"
                value={selectedTierId}
                onChange={(e) => setSelectedTierId(e.target.value)}
              >
                <option value="">Select tier...</option>
                {tiers.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <Button onClick={assignTier} disabled={assigning || !selectedTierId}>
                {assigning ? "Assigning..." : "Assign"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
