"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import {
  PlusCircle, Video, RefreshCw, Copy, AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface VideoConsultation {
  id: string;
  customer_id: string;
  staff_user_id: string | null;
  scheduled_for: string | null;
  status: "scheduled" | "active" | "ended" | "cancelled";
  provider: "daily" | "twilio";
  duration_seconds: number | null;
  notes: string | null;
  customer_join_token: string | null;
  staff_join_token: string | null;
  created_at: string;
}

type StatusFilter = "all" | "scheduled" | "active" | "ended" | "cancelled";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scheduled", label: "Scheduled" },
  { value: "active", label: "Active" },
  { value: "ended", label: "Ended" },
  { value: "cancelled", label: "Cancelled" },
];

const STATUS_BADGE: Record<string, string> = {
  scheduled:  "bg-blue-100 text-blue-700",
  active:     "bg-green-100 text-green-700",
  ended:      "bg-gray-100 text-gray-500",
  cancelled:  "bg-red-100 text-red-600",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  scheduled: "statusScheduled",
  active:    "statusActive",
  ended:     "statusEnded",
  cancelled: "statusCancelled",
};

const PROVIDER_BADGE: Record<string, string> = {
  daily:  "bg-violet-100 text-violet-700",
  twilio: "bg-orange-100 text-orange-700",
};

const PROVIDER_MODULE: Record<string, keyof typeof styles> = {
  daily:  "providerDaily",
  twilio: "providerTwilio",
};

function formatDuration(secs: number | null): string {
  if (secs === null) return "";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}m ${s}s`;
}

function formatDt(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function truncate(str: string | null, n: number): string {
  if (!str) return "—";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

export default function VideoConsultationsPage() {
  const [consultations, setConsultations] = useState<VideoConsultation[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    customer_id: "",
    scheduled_for: "",
    provider: "daily",
    notes: "",
    staff_user_id: "",
  });
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<VideoConsultation[]>("/api/video");
      setConsultations(data);
    } catch {
      toast.error("Failed to load video consultations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function doAction(id: string, action: "start" | "end" | "cancel") {
    setActionLoading(id + "_" + action);
    try {
      await api.post(`/api/video/${id}/${action}`, {});
      toast.success(`Consultation ${action}ed`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `Failed to ${action} consultation`);
    } finally {
      setActionLoading(null);
    }
  }

  async function createConsultation() {
    if (!newForm.customer_id.trim()) { toast.error("Customer ID is required"); return; }
    if (!newForm.scheduled_for) { toast.error("Scheduled date/time is required"); return; }
    setActionLoading("create");
    try {
      await api.post("/api/video", {
        customer_id: newForm.customer_id,
        scheduled_for: newForm.scheduled_for,
        provider: newForm.provider,
        notes: newForm.notes || null,
        staff_user_id: newForm.staff_user_id || null,
      });
      toast.success("Consultation scheduled");
      setShowNew(false);
      setNewForm({ customer_id: "", scheduled_for: "", provider: "daily", notes: "", staff_user_id: "" });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function copyToClipboard(text: string | null, label: string) {
    if (!text) { toast.error("Token not available"); return; }
    navigator.clipboard.writeText(text).then(() => toast.success(`${label} copied`));
  }

  const filtered =
    statusFilter === "all" ? consultations : consultations.filter((c) => c.status === statusFilter);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Video Consultations</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Schedule and manage video sessions with customers.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Schedule Consultation
        </Button>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-2.5 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
        <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-blue-800">
          Rooms are hosted on Daily.co. Distribute join tokens to participants before the session.
        </p>
      </div>

      {/* Status filter tabs */}
      <div className="flex items-center gap-1 border-b">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setStatusFilter(t.value)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              statusFilter === t.value
                ? "border-[#1a2332] text-[#1a2332]"
                : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* New consultation form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Schedule Video Consultation</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Customer ID (UUID) *</label>
              <input
                value={newForm.customer_id}
                onChange={(e) => setNewForm((f) => ({ ...f, customer_id: e.target.value }))}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Scheduled For *</label>
              <input
                type="datetime-local"
                value={newForm.scheduled_for}
                onChange={(e) => setNewForm((f) => ({ ...f, scheduled_for: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Provider</label>
              <select
                value={newForm.provider}
                onChange={(e) => setNewForm((f) => ({ ...f, provider: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332] bg-white"
              >
                <option value="daily">Daily.co</option>
                <option value="twilio">Twilio</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Staff User ID (optional)</label>
              <input
                value={newForm.staff_user_id}
                onChange={(e) => setNewForm((f) => ({ ...f, staff_user_id: e.target.value }))}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Notes (optional)</label>
            <textarea
              value={newForm.notes}
              onChange={(e) => setNewForm((f) => ({ ...f, notes: e.target.value }))}
              rows={2}
              placeholder="Pre-session notes…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "create"}
              onClick={createConsultation}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
            >
              {actionLoading === "create" ? "Scheduling…" : "Schedule"}
            </Button>
          </div>
        </div>
      )}

      {/* Consultations list */}
      {loading && consultations.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <Video className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No consultations found</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {filtered.map((c) => (
            <div key={c.id} className="flex items-center gap-4 px-5 py-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                  <p className="text-sm font-medium text-gray-900">
                    {truncate(c.customer_id, 18)}
                  </p>
                  <span className={styles[STATUS_MODULE[c.status] ?? "statusEnded"]}>
                    {c.status === "active" ? (
                      <span className="flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                        {c.status}
                      </span>
                    ) : c.status}
                  </span>
                  <span className={styles[PROVIDER_MODULE[c.provider] ?? "providerDaily"]}>
                    {c.provider === "daily" ? "Daily.co" : "Twilio"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatDt(c.scheduled_for)}
                  {c.staff_user_id ? ` · Staff: ${truncate(c.staff_user_id, 12)}` : ""}
                  {c.duration_seconds ? ` · ${formatDuration(c.duration_seconds)}` : ""}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
                {c.status === "scheduled" && (
                  <>
                    <Button
                      size="sm"
                      disabled={actionLoading === c.id + "_start"}
                      onClick={() => doAction(c.id, "start")}
                      className="bg-green-600 hover:bg-green-700 text-white gap-1"
                    >
                      {actionLoading === c.id + "_start" ? <RefreshCw className="h-3 w-3 animate-spin" /> : null}
                      Start
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={actionLoading === c.id + "_cancel"}
                      onClick={() => doAction(c.id, "cancel")}
                      className="border-red-200 text-red-600 hover:bg-red-50"
                    >
                      Cancel
                    </Button>
                  </>
                )}
                {c.status === "active" && (
                  <Button
                    size="sm"
                    disabled={actionLoading === c.id + "_end"}
                    onClick={() => doAction(c.id, "end")}
                    className="bg-gray-700 hover:bg-gray-800 text-white gap-1"
                  >
                    {actionLoading === c.id + "_end" ? <RefreshCw className="h-3 w-3 animate-spin" /> : null}
                    End
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(c.customer_join_token, "Customer link")}
                  className="gap-1 text-xs"
                >
                  <Copy className="h-3 w-3" /> Customer Link
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(c.staff_join_token, "Staff link")}
                  className="gap-1 text-xs"
                >
                  <Copy className="h-3 w-3" /> Staff Link
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
