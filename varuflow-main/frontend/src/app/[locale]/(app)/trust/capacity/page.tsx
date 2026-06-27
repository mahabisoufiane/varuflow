"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";

interface CapacityResult {
  total_slots: number;
  booked: number;
  remaining: number;
  period_type: string;
  show_urgency: boolean;
}

export default function CapacityPage() {
  // Check section
  const [checkServiceId, setCheckServiceId] = useState("");
  const [checkStaffId, setCheckStaffId] = useState("");
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkError, setCheckError] = useState("");
  const [capacityResult, setCapacityResult] = useState<CapacityResult | null>(null);

  // Config section
  const [configForm, setConfigForm] = useState({
    service_id: "",
    staff_id: "",
    period_type: "week",
    total_slots: "",
    show_urgency_below: "",
  });
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState("");
  const [configSuccess, setConfigSuccess] = useState(false);

  async function handleCheck() {
    setCheckLoading(true);
    setCheckError("");
    setCapacityResult(null);
    try {
      const qs = new URLSearchParams();
      if (checkServiceId) qs.set("service_id", checkServiceId);
      if (checkStaffId) qs.set("staff_id", checkStaffId);
      setCapacityResult(await api.get<CapacityResult>(`/api/booking-capacity?${qs}`));
    } catch (e: unknown) {
      setCheckError(e instanceof Error ? e.message : "Failed to fetch capacity");
    } finally {
      setCheckLoading(false);
    }
  }

  async function handleSaveConfig() {
    setConfigLoading(true);
    setConfigError("");
    setConfigSuccess(false);
    try {
      const body: Record<string, unknown> = {
        period_type: configForm.period_type,
        total_slots: Number(configForm.total_slots),
      };
      if (configForm.service_id) body.service_id = configForm.service_id;
      if (configForm.staff_id) body.staff_id = configForm.staff_id;
      if (configForm.show_urgency_below)
        body.show_urgency_below = Number(configForm.show_urgency_below);

      await api.put<unknown>("/api/booking-capacity", body);
      setConfigSuccess(true);
    } catch (e: unknown) {
      setConfigError(e instanceof Error ? e.message : "Failed to save configuration");
    } finally {
      setConfigLoading(false);
    }
  }

  const pct =
    capacityResult && capacityResult.total_slots > 0
      ? Math.round((capacityResult.booked / capacityResult.total_slots) * 100)
      : 0;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Booking Capacity</h1>

      {/* Live Check */}
      <Card>
        <CardHeader><CardTitle>Live Capacity Check</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Service ID</label>
              <Input
                value={checkServiceId}
                onChange={(e) => setCheckServiceId(e.target.value)}
                placeholder="UUID (optional)"
                className="w-56"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Staff ID</label>
              <Input
                value={checkStaffId}
                onChange={(e) => setCheckStaffId(e.target.value)}
                placeholder="UUID (optional)"
                className="w-56"
              />
            </div>
            <Button onClick={handleCheck} disabled={checkLoading}>
              {checkLoading ? "Checking…" : "Check"}
            </Button>
          </div>

          {checkError && <p className="text-red-500 text-sm">{checkError}</p>}

          {capacityResult && (
            <div className="space-y-3">
              {capacityResult.show_urgency && capacityResult.remaining <= (capacityResult.total_slots * 0.2) && (
                <div className="rounded-md bg-yellow-50 border border-yellow-200 px-4 py-2 text-sm text-yellow-800">
                  Only {capacityResult.remaining} slots left this week!
                </div>
              )}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <p className="text-3xl font-bold">{capacityResult.total_slots}</p>
                  <p className="text-xs text-muted-foreground">Total Slots</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold">{capacityResult.booked}</p>
                  <p className="text-xs text-muted-foreground">Booked</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-600">{capacityResult.remaining}</p>
                  <p className="text-xs text-muted-foreground">Remaining</p>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                  <span>Utilisation</span>
                  <span>{pct}%</span>
                </div>
                <div className="h-3 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${pct >= 80 ? "bg-red-500" : pct >= 60 ? "bg-yellow-400" : "bg-green-500"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
              <Badge variant="outline">{capacityResult.period_type} period</Badge>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configure */}
      <Card>
        <CardHeader><CardTitle>Configure Capacity</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Service ID (optional)</label>
              <Input
                value={configForm.service_id}
                onChange={(e) => setConfigForm((f) => ({ ...f, service_id: e.target.value }))}
                placeholder="UUID"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Staff ID (optional)</label>
              <Input
                value={configForm.staff_id}
                onChange={(e) => setConfigForm((f) => ({ ...f, staff_id: e.target.value }))}
                placeholder="UUID"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Period Type *</label>
              <select
                value={configForm.period_type}
                onChange={(e) => setConfigForm((f) => ({ ...f, period_type: e.target.value }))}
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm w-full"
              >
                <option value="week">Week</option>
                <option value="day">Day</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Total Slots *</label>
              <Input
                type="number"
                min="1"
                value={configForm.total_slots}
                onChange={(e) => setConfigForm((f) => ({ ...f, total_slots: e.target.value }))}
                placeholder="e.g. 20"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Show Urgency Below</label>
              <Input
                type="number"
                min="0"
                value={configForm.show_urgency_below}
                onChange={(e) =>
                  setConfigForm((f) => ({ ...f, show_urgency_below: e.target.value }))
                }
                placeholder="e.g. 3"
              />
            </div>
          </div>

          {configError && <p className="text-red-500 text-sm">{configError}</p>}
          {configSuccess && (
            <p className="text-green-600 text-sm font-medium">Configuration saved</p>
          )}

          <Button onClick={handleSaveConfig} disabled={configLoading}>
            {configLoading ? "Saving…" : "Save Configuration"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
