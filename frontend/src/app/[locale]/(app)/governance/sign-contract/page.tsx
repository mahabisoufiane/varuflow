"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { FileSignature, Check, Shield, AlertTriangle, CalendarDays } from "lucide-react";

interface Contract {
  id: string; title: string; status: string;
  customer_id: string; start_date: string | null; end_date: string | null;
  value_amount: number; currency: string;
  signed_at: string | null; signer_name: string | null; signer_email: string | null; signature_hash: string | null;
}

interface SignatureRecord {
  signed: boolean;
  signer_name?: string; signer_email?: string; signed_at?: string; signature_hash?: string;
  verification_note?: string;
}

export default function SignContractPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const f = (url: string, init?: RequestInit) => fetch(`${apiBase}${url}`, { credentials: "include", ...init });

  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sigRecord, setSigRecord] = useState<SignatureRecord | null>(null);
  const [signerName, setSignerName] = useState("");
  const [signerEmail, setSignerEmail] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [signing, setSigning] = useState(false);
  const [filterStatus, setFilterStatus] = useState("ACTIVE");

  useEffect(() => {
    f(`/api/contracts?status=${filterStatus}`).then(r => r.ok ? r.json() : []).then((data: Contract[]) => {
      setContracts(data);
      setLoading(false);
    });
  }, [filterStatus]);

  async function selectContract(id: string) {
    setSelectedId(id);
    setSigRecord(null);
    const res = await f(`/api/contracts/${id}/signature`);
    if (res.ok) setSigRecord(await res.json());
  }

  async function sign() {
    if (!selectedId || !signerName.trim() || !signerEmail.trim()) {
      toast.error("Please enter your full name and email");
      return;
    }
    if (!confirmed) { toast.error("Please confirm you agree to sign"); return; }
    setSigning(true);
    try {
      const res = await f(`/api/contracts/${selectedId}/sign`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signer_name: signerName, signer_email: signerEmail }),
      });
      if (!res.ok) {
        const e = await res.json();
        toast.error(e.detail || "Signing failed");
        return;
      }
      const data = await res.json();
      toast.success("Contract signed successfully");
      setSigRecord({
        signed: true, signer_name: data.signer_name, signer_email: data.signer_email,
        signed_at: data.signed_at, signature_hash: data.signature_hash,
      });
      // Update contract in list
      setContracts(prev => prev.map(c => c.id === selectedId ? { ...c, status: data.status, signed_at: data.signed_at, signer_name: data.signer_name } : c));
      setSignerName(""); setSignerEmail(""); setConfirmed(false);
    } finally {
      setSigning(false);
    }
  }

  const selected = contracts.find(c => c.id === selectedId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Sign Contracts</h1>
        <p className="mt-1 text-sm text-gray-500">Apply a legally binding electronic signature (Simple Electronic Signature — EU eIDAS) to any contract stored in Varuflow.</p>
      </div>

      {/* Status filter */}
      <div className="flex gap-2">
        {["DRAFT", "ACTIVE"].map(s => (
          <button key={s} onClick={() => { setFilterStatus(s); setSelectedId(null); setSigRecord(null); }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${filterStatus === s ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
            {s.charAt(0) + s.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contract list */}
        <div className="space-y-2">
          {loading && [1,2,3].map(i => <div key={i} className="animate-pulse h-20 rounded-xl bg-gray-100" />)}
          {!loading && contracts.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <FileSignature className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p>No {filterStatus.toLowerCase()} contracts found.</p>
            </div>
          )}
          {contracts.map(c => (
            <button key={c.id} onClick={() => selectContract(c.id)}
              className={`w-full rounded-xl border p-4 text-left transition-all ${
                selectedId === c.id ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"
              }`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{c.title}</p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${c.status === "ACTIVE" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>{c.status}</span>
                    {c.start_date && <span className="text-xs text-gray-400 flex items-center gap-1"><CalendarDays className="h-3 w-3" />{c.start_date}</span>}
                    <span className="text-xs text-gray-400">{c.value_amount.toLocaleString("sv-SE")} {c.currency}</span>
                  </div>
                </div>
                {c.signed_at ? (
                  <div className="flex items-center gap-1 text-green-600 flex-shrink-0">
                    <Check className="h-4 w-4" />
                    <span className="text-xs font-medium">Signed</span>
                  </div>
                ) : (
                  <span className="text-xs text-amber-600 flex-shrink-0">Unsigned</span>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Signing panel */}
        {selected && (
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="bg-gray-50 px-5 py-3 border-b border-gray-100">
              <p className="font-semibold text-gray-800">{selected.title}</p>
            </div>

            <div className="p-5 space-y-5">
              {sigRecord?.signed ? (
                /* Already signed — show certificate */
                <div className="space-y-4">
                  <div className="rounded-xl border border-green-200 bg-green-50 p-4 flex items-start gap-3">
                    <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-green-800">Contract Signed</p>
                      <p className="text-sm text-green-700 mt-0.5">This contract has been digitally signed.</p>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-gray-500">Signed by</span><span className="font-medium text-gray-900">{sigRecord.signer_name}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Email</span><span className="font-medium text-gray-900">{sigRecord.signer_email}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Signed at</span><span className="font-medium text-gray-900">{sigRecord.signed_at ? new Date(sigRecord.signed_at).toLocaleString("sv-SE") : "—"}</span></div>
                    <div className="pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-400 mb-1">Signature hash (SHA-256)</p>
                      <p className="text-xs font-mono text-gray-600 break-all bg-gray-50 rounded p-2">{sigRecord.signature_hash}</p>
                    </div>
                  </div>
                  {sigRecord.verification_note && (
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 flex items-start gap-2">
                      <Shield className="h-4 w-4 text-blue-400 flex-shrink-0 mt-0.5" />
                      <p className="text-xs text-gray-500">{sigRecord.verification_note}</p>
                    </div>
                  )}
                </div>
              ) : (
                /* Signing form */
                <div className="space-y-4">
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-700">
                      By typing your name and clicking Sign, you are applying a Simple Electronic Signature (SES)
                      under EU eIDAS. Your name, email, and a tamper-evident hash will be permanently recorded.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="text-sm font-medium text-gray-700 block mb-1">Full name *</label>
                      <input
                        className="input w-full"
                        placeholder="Type your full legal name to sign"
                        value={signerName}
                        onChange={e => setSignerName(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700 block mb-1">Email address *</label>
                      <input
                        className="input w-full"
                        type="email"
                        placeholder="Your work email address"
                        value={signerEmail}
                        onChange={e => setSignerEmail(e.target.value)}
                      />
                    </div>
                    <label className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={e => setConfirmed(e.target.checked)}
                        className="mt-0.5 rounded flex-shrink-0"
                      />
                      <span className="text-sm text-gray-700">
                        I confirm that I have read this contract and I intend to be legally bound by its terms.
                        I understand this constitutes a valid electronic signature.
                      </span>
                    </label>
                  </div>

                  <button
                    onClick={sign}
                    disabled={signing || !signerName.trim() || !signerEmail.trim() || !confirmed}
                    className="btn-primary flex items-center gap-2 w-full justify-center py-3"
                  >
                    <FileSignature className="h-4 w-4" />
                    {signing ? "Signing…" : "Sign Contract"}
                  </button>

                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <Shield className="h-3.5 w-3.5 flex-shrink-0" />
                    <span>Simple Electronic Signature per EU eIDAS Regulation 910/2014 · SHA-256 tamper detection</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
