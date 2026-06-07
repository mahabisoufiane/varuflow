"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Eye, Send, Clock, Trash2 } from "lucide-react";
import { toast } from "sonner";
import styles from "./page.module.scss";

const STATUS_MODULE: Record<string, keyof typeof styles> = { SENT: "statusSent", SCHEDULED: "statusScheduled" };

interface Campaign {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  segment_id: string | null;
  status: "DRAFT" | "SCHEDULED" | "SENT";
  scheduled_at: string | null;
  sent_at: string | null;
  recipient_count: number;
}

interface Stats {
  total: number;
  sent: number;
  failed: number;
  bounced: number;
  opened: number;
  open_rate: number;
  bounce_rate: number;
}

function StatusBadge({ status }: { status: Campaign["status"] }) {
  if (status === "SENT") return <span className={styles[STATUS_MODULE["SENT"] ?? "statusDefault"]}>Sent</span>;
  if (status === "SCHEDULED") return <span className={styles[STATUS_MODULE["SCHEDULED"] ?? "statusDefault"]}>Scheduled</span>;
  return <span className={styles.statusDefault}>Draft</span>;
}

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params.id);

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [scheduleWhen, setScheduleWhen] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const c = await api.get<Campaign>(`/api/campaigns/${id}`);
      setCampaign(c);
      if (c.status === "SENT") {
        setStats(await api.get<Stats>(`/api/campaigns/${id}/stats`));
      }
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function runPreview() {
    setBusy(true);
    try {
      const r = await api.post<{ body_html: string; recipient_count: number }>(
        `/api/campaigns/${id}/preview`,
        {},
      );
      setPreview(r.body_html);
      toast.success(`${r.recipient_count} recipient(s) ready`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendNow() {
    if (!confirm("Send this campaign now? This cannot be undone.")) return;
    setBusy(true);
    try {
      await api.post(`/api/campaigns/${id}/send`, {});
      toast.success("Campaign sent");
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function schedule() {
    if (!scheduleWhen) {
      toast.error("Pick a date/time");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/api/campaigns/${id}/schedule`, {
        scheduled_at: new Date(scheduleWhen).toISOString(),
      });
      toast.success("Scheduled");
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this campaign?")) return;
    try {
      await api.delete(`/api/campaigns/${id}`);
      toast.success("Deleted");
      router.push("/campaigns");
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  if (!campaign) {
    return <div className="h-40 animate-pulse rounded-xl bg-gray-100" />;
  }

  const canEdit = campaign.status !== "SENT";

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">{campaign.name}</h1>
          <div className="mt-1 flex items-center gap-3 text-sm">
            <StatusBadge status={campaign.status} />
            <span className="text-muted-foreground">Subject: {campaign.subject}</span>
          </div>
        </div>
        {canEdit && (
          <Button variant="ghost" size="sm" onClick={remove} className="text-red-600">
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Delete
          </Button>
        )}
      </div>

      {stats && (
        <div className="rounded-xl border bg-white p-5 grid grid-cols-4 gap-4 text-sm">
          <div><div className="text-xs text-muted-foreground">Recipients</div><div className="font-semibold">{stats.total}</div></div>
          <div><div className="text-xs text-muted-foreground">Delivered</div><div className="font-semibold">{stats.sent}</div></div>
          <div><div className="text-xs text-muted-foreground">Open rate</div><div className="font-semibold">{(stats.open_rate * 100).toFixed(1)}%</div></div>
          <div><div className="text-xs text-muted-foreground">Bounce rate</div><div className="font-semibold">{(stats.bounce_rate * 100).toFixed(1)}%</div></div>
        </div>
      )}

      <div className="rounded-xl border bg-white p-5 space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={runPreview} disabled={busy}>
            <Eye className="mr-1.5 h-3.5 w-3.5" />
            Preview
          </Button>
          {canEdit && campaign.segment_id && (
            <>
              <Button
                size="sm"
                className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
                onClick={sendNow}
                disabled={busy}
              >
                <Send className="mr-1.5 h-3.5 w-3.5" />
                Send now
              </Button>
              <div className="flex items-center gap-1">
                <input
                  type="datetime-local"
                  value={scheduleWhen}
                  onChange={(e) => setScheduleWhen(e.target.value)}
                  className="rounded-md border px-2 py-1 text-sm"
                />
                <Button size="sm" variant="secondary" onClick={schedule} disabled={busy}>
                  <Clock className="mr-1.5 h-3.5 w-3.5" />
                  Schedule
                </Button>
              </div>
            </>
          )}
        </div>
        {!campaign.segment_id && canEdit && (
          <p className="text-xs text-amber-700">
            This campaign has no segment attached — pick one before sending.
          </p>
        )}
      </div>

      {preview && (
        <div className="rounded-xl border bg-white p-5">
          <h3 className="mb-3 font-medium text-[#1a2332]">Preview</h3>
          <div
            className="prose prose-sm max-w-none rounded border bg-white p-4"
            dangerouslySetInnerHTML={{ __html: preview }}
          />
        </div>
      )}
    </div>
  );
}
