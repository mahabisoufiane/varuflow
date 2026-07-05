"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { Copy, FileText, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

/* ── Types ─────────────────────────────────────────────────────────────────── */
interface Customer {
  id: string;
  company_name: string;
}
interface DraftResponse {
  draft_body: string;
  contract_type: string;
  customer_name: string;
}

const CONTRACT_TYPES = [
  { value: "service_agreement",     label: "Service Agreement"       },
  { value: "supply_agreement",      label: "Supply Agreement"        },
  { value: "nda",                   label: "Non-Disclosure Agreement" },
  { value: "framework_agreement",   label: "Framework Agreement"     },
  { value: "distribution_agreement", label: "Distribution Agreement" },
];

/* ── Page ───────────────────────────────────────────────────────────────────── */
export default function ContractsPage() {
  const locale = useLocale();
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [contractType, setContractType] = useState("service_agreement");
  const [keyTerms, setKeyTerms] = useState("");
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    api.get("/api/invoicing/customers?limit=500&offset=0")
      .then((d: unknown) => setCustomers((d as { customers: Customer[] }).customers ?? []))
      .catch((e: unknown) => {
        const err = e as { status?: number };
        if (err.status === 401) router.push("/auth/login");
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function generate() {
    if (!customerId) { toast.error("Please select a customer."); return; }
    setGenerating(true);
    setDraft(null);
    try {
      const d = await api.post("/api/ai/contracts/draft", {
        customer_id: customerId,
        contract_type: contractType,
        key_terms: keyTerms,
      });
      setDraft(d as DraftResponse);
    } catch (e: unknown) {
      const err = e as { status?: number; detail?: string };
      if (err.status === 401) router.push("/auth/login");
      else if (err.status === 403) toast.error("Contract drafting requires a Pro plan.");
      else toast.error("Failed to generate contract.");
    } finally {
      setGenerating(false);
    }
  }

  function copyToClipboard() {
    if (!draft) return;
    navigator.clipboard.writeText(draft.draft_body);
    toast.success("Copied to clipboard.");
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileText className="w-6 h-6 text-emerald-500" />
          AI Contract Drafting
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Generate a first-draft contract using customer data and your key terms — powered by GPT-4o.
        </p>
      </div>

      {/* Form */}
      <div className="p-5 border rounded-lg space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Customer *</label>
            <select
              value={customerId}
              onChange={e => setCustomerId(e.target.value)}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
            >
              <option value="">Select customer…</option>
              {customers.map(c => (
                <option key={c.id} value={c.id}>{c.company_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium">Contract type</label>
            <select
              value={contractType}
              onChange={e => setContractType(e.target.value)}
              className="mt-1 w-full border rounded px-3 py-2 text-sm"
            >
              {CONTRACT_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="text-sm font-medium">Key terms &amp; special clauses (optional)</label>
          <textarea
            value={keyTerms}
            onChange={e => setKeyTerms(e.target.value)}
            rows={4}
            className="mt-1 w-full border rounded px-3 py-2 text-sm"
            placeholder="E.g. 12-month exclusivity in Sweden, net-30 payment, annual price revision in January, automatic renewal…"
          />
        </div>

        <button
          onClick={generate}
          disabled={generating || !customerId}
          className="flex items-center gap-2 px-5 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {generating ? "Generating…" : "Generate Draft"}
        </button>
      </div>

      {/* Draft output */}
      {draft && (
        <div className="border rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
            <div>
              <span className="font-medium text-sm">{draft.customer_name}</span>
              <span className="ml-2 text-xs text-gray-400">
                {CONTRACT_TYPES.find(t => t.value === draft.contract_type)?.label ?? draft.contract_type}
              </span>
            </div>
            <button
              onClick={copyToClipboard}
              className="flex items-center gap-1.5 text-xs px-3 py-1 border rounded hover:bg-white"
            >
              <Copy className="w-3 h-3" /> Copy
            </button>
          </div>
          <pre className="p-5 text-sm leading-relaxed whitespace-pre-wrap font-sans text-gray-800 max-h-[60vh] overflow-y-auto">
            {draft.draft_body}
          </pre>
        </div>
      )}
    </div>
  );
}
