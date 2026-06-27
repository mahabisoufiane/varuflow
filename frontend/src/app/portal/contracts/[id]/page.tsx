"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";

interface NdaDetail { id: string; title: string; body: string; status: string; signed_at: string | null; }

export default function PortalContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [nda, setNda] = useState<NdaDetail | null>(null);
  const [signerName, setSignerName] = useState("");
  const [signerEmail, setSignerEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<NdaDetail>(`/api/portal/contracts/${id}`).then(setNda).catch(() => toast.error("Not found"));
  }, [id]);

  const sign = async () => {
    if (!signerName.trim() || !signerEmail.trim()) { toast.error("Name and email required"); return; }
    setSubmitting(true);
    try {
      await portalApi.post(`/api/portal/contracts/${id}/sign`, { signer_name: signerName, signer_email: signerEmail });
      toast.success("Contract signed");
      setNda(d => d ? { ...d, status: "signed", signed_at: new Date().toISOString() } : d);
    } catch {
      toast.error("Failed to sign contract");
    } finally {
      setSubmitting(false);
    }
  };

  if (!nda) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{nda.title}</h1>
      {nda.status === "signed" && (
        <div className="rounded bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          ✓ Signed on {new Date(nda.signed_at!).toLocaleDateString()}
        </div>
      )}
      <div className="prose prose-sm max-w-none border rounded p-4 bg-white whitespace-pre-wrap text-sm text-gray-700 max-h-96 overflow-y-auto">
        {nda.body}
      </div>
      {nda.status === "pending" && (
        <div className="border rounded p-4 space-y-3">
          <h2 className="font-semibold text-sm">Sign this contract</h2>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input
              className="border rounded px-3 py-2 text-sm w-full"
              placeholder="Full name"
              value={signerName}
              onChange={e => setSignerName(e.target.value)}
            />
            <input
              className="border rounded px-3 py-2 text-sm w-full"
              placeholder="Email address"
              type="email"
              value={signerEmail}
              onChange={e => setSignerEmail(e.target.value)}
            />
          </div>
          <p className="text-xs text-gray-400">By clicking Sign, you agree to the terms above.</p>
          <button
            onClick={sign}
            disabled={submitting}
            className="px-4 py-2 bg-[#1a2332] text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Signing…" : "Sign Contract"}
          </button>
        </div>
      )}
    </div>
  );
}
