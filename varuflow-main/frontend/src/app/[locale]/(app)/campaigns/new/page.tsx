"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

interface Segment {
  id: string;
  name: string;
  type: string;
  customer_count: number;
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [bodyHtml, setBodyHtml] = useState(
    '<p>Hi there,</p>\n<p>We wanted to share some news...</p>\n<p>Thanks!</p>',
  );
  const [segmentId, setSegmentId] = useState<string>("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<Segment[]>("/api/segments").then(setSegments).catch(() => {});
  }, []);

  async function submit() {
    if (!name.trim() || !subject.trim()) {
      toast.error("Name and subject required");
      return;
    }
    setSaving(true);
    try {
      const res = await api.post<{ id: string }>("/api/campaigns", {
        name: name.trim(),
        subject: subject.trim(),
        body_html: bodyHtml,
        segment_id: segmentId || null,
      });
      toast.success("Draft saved");
      router.push(`/campaigns/${res.id}`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">New campaign</h1>
        <p className="text-sm text-muted-foreground">
          Target a customer segment with a broadcast email. You can preview
          and schedule before sending.
        </p>
      </div>

      <div className="rounded-xl border bg-white p-5 space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Campaign name (internal)</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="October product launch"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Email subject</label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="Check out what's new"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Target segment</label>
          <select
            value={segmentId}
            onChange={(e) => setSegmentId(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm bg-white"
          >
            <option value="">— choose later —</option>
            {segments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.type}, {s.customer_count})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Body (HTML, rich text)
          </label>
          <textarea
            value={bodyHtml}
            onChange={(e) => setBodyHtml(e.target.value)}
            rows={12}
            className="w-full rounded-md border px-3 py-2 text-sm font-mono"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            A GDPR-compliant unsubscribe footer is added automatically.
          </p>
        </div>

        <div className="flex gap-2 pt-2">
          <Button onClick={submit} disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            Save draft
          </Button>
          <Button variant="ghost" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
