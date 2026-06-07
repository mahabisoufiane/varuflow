"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Mail, Plus, Send, Clock } from "lucide-react";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface Campaign {
  id: string;
  name: string;
  subject: string;
  segment_id: string | null;
  status: "DRAFT" | "SCHEDULED" | "SENT";
  scheduled_at: string | null;
  sent_at: string | null;
  recipient_count: number;
  created_at: string;
}

function StatusBadge({ status }: { status: Campaign["status"] }) {
  if (status === "SENT") return <span className={styles.badgeSent}>Sent</span>;
  if (status === "SCHEDULED") return <span className={styles.badgeScheduled}>Scheduled</span>;
  return <span className={styles.badgeDraft}>Draft</span>;
}

export default function CampaignsListPage() {
  const [rows, setRows] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setRows(await api.get<Campaign[]>("/api/campaigns"));
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Email campaigns</h1>
          <p className="text-sm text-muted-foreground">
            {rows.length} campaign{rows.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
          <Link href="/campaigns/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            New campaign
          </Link>
        </Button>
      </div>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-xl bg-gray-100" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className={styles.emptyState}>
          <Mail className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No campaigns yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Target a customer segment with a broadcast email.
          </p>
          <Button asChild size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white">
            <Link href="/campaigns/new">
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              New campaign
            </Link>
          </Button>
        </div>
      ) : (
        <div className={styles.tableCard}>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Subject</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Recipients</th>
                <th className="px-4 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className={styles.tableRow}>
                  <td className="px-4 py-3">
                    <Link href={`/campaigns/${c.id}`} className="font-medium text-[#1a2332] hover:underline">
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground truncate max-w-xs">{c.subject}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-3">{c.recipient_count}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {c.sent_at ? (
                      <span className="inline-flex items-center gap-1"><Send className="h-3 w-3" />{new Date(c.sent_at).toLocaleString()}</span>
                    ) : c.scheduled_at ? (
                      <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(c.scheduled_at).toLocaleString()}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
