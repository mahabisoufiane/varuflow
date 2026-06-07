"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Prefs {
  favorite_staff_user_id: string;
  preferred_time_of_day: string;
  preferred_day_of_week: string;
  allergies: string;
  communication_channel: string;
  notes: string;
}

const defaultPrefs: Prefs = {
  favorite_staff_user_id: "",
  preferred_time_of_day: "any",
  preferred_day_of_week: "0",
  allergies: "",
  communication_channel: "email",
  notes: "",
};

export default function PreferencesPage() {
  const [customerId, setCustomerId] = useState("");
  const [prefs, setPrefs] = useState<Prefs>(defaultPrefs);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loaded, setLoaded] = useState(false);

  async function handleLoad() {
    if (!customerId.trim()) return;
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const data = await api.get<Prefs>(`/api/preferences/${customerId}`);
      setPrefs({ ...defaultPrefs, ...data });
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load preferences.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await api.put(`/api/preferences/${customerId}`, prefs);
      setSuccess("Preferences saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save preferences.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Customer Preferences</h1>
      <p className="text-muted-foreground">View and edit a customer&apos;s preferences (favorite stylist, preferred time, allergies, communication channel).</p>

      <Card>
        <CardHeader><CardTitle>Load Customer</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer UUID"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={handleLoad} disabled={loading}>
              {loading ? "Loading..." : "Load"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {loading && <p className="text-muted-foreground">Loading...</p>}

      {loaded && (
        <Card>
          <CardHeader><CardTitle>Preferences for {customerId}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Favorite Staff User ID</label>
              <Input
                value={prefs.favorite_staff_user_id}
                onChange={(e) => setPrefs({ ...prefs, favorite_staff_user_id: e.target.value })}
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Preferred Time of Day</label>
              <select
                className="w-full border rounded px-3 py-2 text-sm bg-background"
                value={prefs.preferred_time_of_day}
                onChange={(e) => setPrefs({ ...prefs, preferred_time_of_day: e.target.value })}
              >
                <option value="morning">Morning</option>
                <option value="afternoon">Afternoon</option>
                <option value="evening">Evening</option>
                <option value="any">Any</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Preferred Day of Week</label>
              <select
                className="w-full border rounded px-3 py-2 text-sm bg-background"
                value={prefs.preferred_day_of_week}
                onChange={(e) => setPrefs({ ...prefs, preferred_day_of_week: e.target.value })}
              >
                <option value="0">Monday</option>
                <option value="1">Tuesday</option>
                <option value="2">Wednesday</option>
                <option value="3">Thursday</option>
                <option value="4">Friday</option>
                <option value="5">Saturday</option>
                <option value="6">Sunday</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Allergies</label>
              <textarea
                className="w-full border rounded px-3 py-2 text-sm bg-background min-h-[80px]"
                value={prefs.allergies}
                onChange={(e) => setPrefs({ ...prefs, allergies: e.target.value })}
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Communication Channel</label>
              <select
                className="w-full border rounded px-3 py-2 text-sm bg-background"
                value={prefs.communication_channel}
                onChange={(e) => setPrefs({ ...prefs, communication_channel: e.target.value })}
              >
                <option value="push">Push</option>
                <option value="email">Email</option>
                <option value="sms">SMS</option>
                <option value="none">None</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Notes</label>
              <textarea
                className="w-full border rounded px-3 py-2 text-sm bg-background min-h-[80px]"
                value={prefs.notes}
                onChange={(e) => setPrefs({ ...prefs, notes: e.target.value })}
              />
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}
            {success && <p className="text-green-600 text-sm">{success}</p>}

            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save Preferences"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
