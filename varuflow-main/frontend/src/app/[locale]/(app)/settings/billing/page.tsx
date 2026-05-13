"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { Pause, Play, Clock, History, AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";

interface PauseStatus {
  is_paused: boolean;
  paused_at: string | null;
  pause_ends_at: string | null;
  pause_reminder_sent_at: string | null;
  days_remaining: number | null;
}

interface PauseHistory {
  id: string;
  started_at: string;
  ended_at: string | null;
  scheduled_resume_at: string;
  reason: string | null;
  resume_reason: string | null;
  actor_user_id: string | null;
}

export default function BillingSettingsPage() {
  const t = useTranslations("billing_pause");
  const [status, setStatus] = useState<PauseStatus | null>(null);
  const [history, setHistory] = useState<PauseHistory[]>([]);
  const [days, setDays] = useState("30");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  async function load() {
    setError(null);
    try {
      const [s, h] = await Promise.all([
        api.get<PauseStatus>("/api/billing/pause/status"),
        api.get<PauseHistory[]>("/api/billing/pause/history"),
      ]);
      setStatus(s);
      setHistory(h);
    } catch (e: any) {
      setError(e.message || String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handlePause() {
    setLoading(true);
    setError(null);
    try {
      await api.post("/api/billing/pause", {
        days: Number(days),
        reason: reason || null,
      });
      setConfirming(false);
      setReason("");
      await load();
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleResume() {
    setLoading(true);
    setError(null);
    try {
      await api.post("/api/billing/resume", {});
      await load();
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {status?.is_paused ? (
        <div className="rounded-lg border border-amber-500/50 bg-amber-50/60 p-5 dark:bg-amber-950/20">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" />
            <div className="flex-1">
              <div className="font-medium">{t("currently_paused")}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {t("resumes_in", { days: status.days_remaining ?? 0 })}
                {status.pause_ends_at && (
                  <>
                    {" · "}
                    {new Date(status.pause_ends_at).toLocaleDateString()}
                  </>
                )}
              </div>
              <div className="mt-3">
                <Button onClick={handleResume} disabled={loading} className="gap-2">
                  <Play className="h-4 w-4" />
                  {t("resume_now")}
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-start gap-3">
            <Pause className="mt-0.5 h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium">{t("pause_card_title")}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {t("pause_card_subtitle")}
              </div>
              {!confirming ? (
                <Button
                  onClick={() => setConfirming(true)}
                  variant="outline"
                  className="mt-3 gap-2"
                >
                  <Pause className="h-4 w-4" />
                  {t("pause_button")}
                </Button>
              ) : (
                <div className="mt-3 space-y-3">
                  <div>
                    <Label>{t("days_label")}</Label>
                    <Input
                      type="number"
                      min={1}
                      max={90}
                      value={days}
                      onChange={(e) => setDays(e.target.value)}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t("days_help")}
                    </p>
                  </div>
                  <div>
                    <Label>{t("reason_label")}</Label>
                    <Input
                      placeholder={t("reason_placeholder")}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={handlePause} disabled={loading}>
                      {t("confirm_pause")}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => setConfirming(false)}
                      disabled={loading}
                    >
                      {t("cancel")}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="rounded-lg border bg-card">
          <div className="flex items-center gap-2 border-b p-4 text-sm font-medium">
            <History className="h-4 w-4" /> {t("history")}
          </div>
          <div className="divide-y">
            {history.map((h) => (
              <div key={h.id} className="flex items-center justify-between p-4 text-sm">
                <div>
                  <div className="font-medium">
                    {new Date(h.started_at).toLocaleDateString()}
                    {h.ended_at
                      ? ` → ${new Date(h.ended_at).toLocaleDateString()}`
                      : ` → ${t("ongoing")}`}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {h.reason || "—"}
                    {h.resume_reason && (
                      <>
                        {" · "}
                        {t("resume_reason_" + h.resume_reason)}
                      </>
                    )}
                  </div>
                </div>
                {h.ended_at ? (
                  <Badge variant="secondary">{t("closed")}</Badge>
                ) : (
                  <Badge variant="outline" className="gap-1">
                    <Clock className="h-3 w-3" /> {t("active")}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
