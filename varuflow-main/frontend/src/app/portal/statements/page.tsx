"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface Statement { id: string; type: string; invoice_number: string | null; date: string | null; amount: number; status: string; currency: string; }

export default function PortalStatementsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Statement[]>([]);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<Statement[]>("/api/portal/statements").then(setItems);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Account Statements</h1>
      <table className="w-full text-sm border bg-white">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left">Date</th>
            <th className="px-4 py-2 text-left">Invoice #</th>
            <th className="px-4 py-2 text-right">Amount</th>
            <th className="px-4 py-2 text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map(i => (
            <tr key={i.id} className="border-t">
              <td className="px-4 py-2">{i.date}</td>
              <td className="px-4 py-2">{i.invoice_number}</td>
              <td className="px-4 py-2 text-right">{i.amount.toLocaleString()} {i.currency}</td>
              <td className="px-4 py-2"><span className={`px-2 py-0.5 text-xs rounded ${i.status === "PAID" ? "bg-green-100 text-green-800" : i.status === "OVERDUE" ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800"}`}>{i.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
