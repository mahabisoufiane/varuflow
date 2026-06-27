"use client";

import { api } from "@/lib/api-client";
import { useState } from "react";
import { Download, Receipt } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

interface VatBox {
  label: string;
  description: string;
  amount: string;
}

interface VatReturn {
  country: string;
  from_date: string;
  to_date: string;
  boxes: VatBox[];
  net_vat_payable: string;
}

export default function UaeVatPage() {
  const locale = useLocale();
  const router = useRouter();
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
  });
  const [toDate, setToDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VatReturn | null>(null);

  async function compute() {
    setLoading(true);
    try {
      const d = await api.get(`/api/accounting/vat-return?from=${fromDate}&to=${toDate}&country=AE&format=json`);
      setResult(d as VatReturn);
    } catch (e: unknown) {
      const err = e as { status?: number };
      if (err.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to compute VAT return.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadXml() {
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL}/api/accounting/vat-return?from=${fromDate}&to=${toDate}&country=AE&format=xml`;
      const a = document.createElement("a");
      a.href = url;
      a.download = `uae_vat_return_${fromDate}_${toDate}.xml`;
      a.click();
    } catch {
      toast.error("Download failed.");
    }
  }

  const net = result ? parseFloat(result.net_vat_payable) : 0;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Receipt className="w-6 h-6 text-sky-600" />
          UAE VAT Return — FTA Form 201
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Generate UAE Federal Tax Authority VAT Return data from your invoices and expenses.
        </p>
      </div>

      {/* Date range */}
      <div className="p-5 border rounded-lg space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Period from</label>
            <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
              className="mt-1 w-full border rounded px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="text-sm font-medium">Period to</label>
            <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
              className="mt-1 w-full border rounded px-3 py-2 text-sm" />
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={compute} disabled={loading}
            className="px-5 py-2 bg-sky-600 text-white text-sm rounded-lg hover:bg-sky-700 disabled:opacity-50">
            {loading ? "Computing…" : "Compute VAT Return"}
          </button>
          {result && (
            <button onClick={downloadXml} className="flex items-center gap-2 px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">
              <Download className="w-4 h-4" /> Download XML
            </button>
          )}
        </div>
      </div>

      {/* Result table */}
      {result && (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Period: <strong>{result.from_date}</strong> — <strong>{result.to_date}</strong>
          </p>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left px-4 py-2 font-medium w-20">Box</th>
                  <th className="text-left px-4 py-2 font-medium">Description</th>
                  <th className="text-right px-4 py-2 font-medium">Amount (AED)</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {result.boxes.map(box => (
                  <tr key={box.label} className="hover:bg-gray-50/50">
                    <td className="px-4 py-2.5 font-mono text-xs">{box.label}</td>
                    <td className="px-4 py-2.5 text-gray-700">{box.description}</td>
                    <td className="px-4 py-2.5 text-right font-medium">
                      {parseFloat(box.amount).toLocaleString("en-AE", { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Net payable highlight */}
          <div className={`p-4 rounded-lg border ${net > 0 ? "bg-amber-50 border-amber-200" : "bg-green-50 border-green-200"}`}>
            <div className="flex justify-between items-center">
              <span className="font-semibold">Net VAT Payable to FTA</span>
              <span className={`text-xl font-bold ${net > 0 ? "text-amber-700" : "text-green-700"}`}>
                AED {net.toLocaleString("en-AE", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
