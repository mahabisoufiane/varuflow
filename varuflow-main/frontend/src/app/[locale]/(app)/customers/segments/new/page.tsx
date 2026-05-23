"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

type AutoKind =
  | "AUTO_HIGH_VALUE"
  | "AUTO_AT_RISK"
  | "AUTO_NEW"
  | "AUTO_INACTIVE"
  | "AUTO_VIP";

const AUTO_KINDS: { value: AutoKind; label: string; sub: string }[] = [
  { value: "AUTO_HIGH_VALUE", label: "High Value", sub: "LTV ≥ 50 000 SEK" },
  { value: "AUTO_AT_RISK",    label: "At Risk",    sub: "Repeat customer, no purchase in 90+ days" },
  { value: "AUTO_NEW",        label: "New",        sub: "First purchase in last 30 days" },
  { value: "AUTO_INACTIVE",   label: "Inactive",   sub: "No purchase in 180+ days" },
  { value: "AUTO_VIP",        label: "VIP",        sub: "LTV ≥ 100k or 20+ orders" },
];

export default function NewSegmentPage() {
  const router = useRouter();
  const [type, setType] = useState<"AUTO" | "MANUAL">("AUTO");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<AutoKind>("AUTO_HIGH_VALUE");
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!name.trim()) {
      toast.error("Name required");
      return;
    }
    const rules = type === "AUTO" ? { kind } : {};
    setSaving(true);
    try {
      const res = await api.post<{ id: string }>("/api/segments", {
        name: name.trim(),
        description: description || null,
        type,
        rules,
      });
      toast.success("Segment created");
      router.push(`/customers/segments/${res.id}`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">New segment</h1>
        <p className="text-sm text-muted-foreground">
          Auto segments are rule-driven and refreshed nightly. Manual segments
          let you pick customers yourself.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {(["AUTO", "MANUAL"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setType(t)}
            className={`rounded-xl border p-4 text-left transition ${
              type === t
                ? "border-[#1a2332] bg-[#1a2332] text-white"
                : "border-gray-200 bg-white hover:border-gray-300"
            }`}
          >
            <div className="font-semibold">{t === "AUTO" ? "Auto" : "Manual"}</div>
            <div className={`mt-1 text-xs ${type === t ? "text-gray-200" : "text-gray-500"}`}>
              {t === "AUTO"
                ? "Membership follows rules — refreshed nightly."
                : "Pick customers yourself."}
            </div>
          </button>
        ))}
      </div>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Name</span>
        <input
          type="text"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded border px-3 py-2"
          placeholder="e.g. VIP Customers"
        />
      </label>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Description (optional)</span>
        <textarea
          rows={3}
          maxLength={2000}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full rounded border px-3 py-2 text-sm"
        />
      </label>

      {type === "AUTO" && (
        <div className="space-y-2">
          <span className="text-sm font-medium">Rule</span>
          <div className="grid gap-2">
            {AUTO_KINDS.map((k) => (
              <label
                key={k.value}
                className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition ${
                  kind === k.value
                    ? "border-[#1a2332] bg-[#f8fafc]"
                    : "border-gray-200 bg-white hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="kind"
                  value={k.value}
                  checked={kind === k.value}
                  onChange={() => setKind(k.value)}
                  className="mt-1"
                />
                <div>
                  <div className="font-medium text-sm">{k.label}</div>
                  <div className="text-xs text-gray-500">{k.sub}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Button
          onClick={submit}
          disabled={saving}
          className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
        >
          {saving ? "Creating…" : "Create segment"}
        </Button>
        <Button variant="outline" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
