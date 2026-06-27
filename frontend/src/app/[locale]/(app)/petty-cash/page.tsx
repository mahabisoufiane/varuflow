"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

interface PettyCashTxn {
  id: string;
  txn_date: string;
  txn_type: string;
  amount: number;
  description: string | null;
  currency: string;
  created_at: string | null;
}

export default function PettyCashPage() {
  const [txns, setTxns] = useState<PettyCashTxn[]>([]);
  const [balance, setBalance] = useState<{ balance: number; total_deposits: number; total_withdrawals: number } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ txn_date: "", txn_type: "withdrawal", amount: "", description: "" });

  const load = async () => {
    try {
      const [txRes, balRes] = await Promise.all([
        api.get<PettyCashTxn[]>("/api/petty-cash"),
        api.get<{ balance: number; total_deposits: number; total_withdrawals: number }>("/api/petty-cash/balance"),
      ]);
      setTxns(txRes);
      setBalance(balRes);
    } catch {
      toast.error("Failed to load petty cash data");
    }
  };

  useEffect(() => { load(); }, []);

  const create = async () => {
    try {
      await api.post("/api/petty-cash", {
        txn_date: form.txn_date,
        txn_type: form.txn_type,
        amount: parseFloat(form.amount) || 0,
        description: form.description,
      });
      setShowCreate(false);
      setForm({ txn_date: "", txn_type: "withdrawal", amount: "", description: "" });
      load();
    } catch {
      toast.error("Failed to save entry");
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Petty Cash</h1>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Add Entry</button>
      </div>

      {balance && (
        <div className="grid grid-cols-3 gap-4">
          <div className="border rounded p-4 text-center">
            <div className="text-sm text-gray-500">Balance</div>
            <div className="text-2xl font-bold">{balance.balance.toLocaleString()} SEK</div>
          </div>
          <div className="border rounded p-4 text-center">
            <div className="text-sm text-gray-500">Total Deposits</div>
            <div className="text-xl text-green-600">{balance.total_deposits.toLocaleString()}</div>
          </div>
          <div className="border rounded p-4 text-center">
            <div className="text-sm text-gray-500">Total Withdrawals</div>
            <div className="text-xl text-red-600">{balance.total_withdrawals.toLocaleString()}</div>
          </div>
        </div>
      )}

      {showCreate && (
        <div className="border rounded p-4 space-y-2 bg-white">
          <input type="date" value={form.txn_date} onChange={e => setForm({ ...form, txn_date: e.target.value })} className="w-full border rounded px-3 py-2" />
          <select value={form.txn_type} onChange={e => setForm({ ...form, txn_type: e.target.value })} className="w-full border rounded px-3 py-2">
            <option value="deposit">Deposit</option>
            <option value="withdrawal">Withdrawal</option>
          </select>
          <input placeholder="Amount" type="number" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} className="w-full border rounded px-3 py-2" />
          <input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full border rounded px-3 py-2" />
          <div className="flex gap-2">
            <button onClick={create} className="px-4 py-2 bg-green-600 text-white rounded">Save</button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 bg-gray-200 rounded">Cancel</button>
          </div>
        </div>
      )}

      <table className="w-full text-sm border">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left">Date</th>
            <th className="px-4 py-2 text-left">Type</th>
            <th className="px-4 py-2 text-right">Amount</th>
            <th className="px-4 py-2 text-left">Description</th>
          </tr>
        </thead>
        <tbody>
          {txns.map(t => (
            <tr key={t.id} className="border-t">
              <td className="px-4 py-2">{t.txn_date}</td>
              <td className="px-4 py-2">
                <span className={`px-2 py-0.5 rounded text-xs ${t.txn_type === "deposit" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>{t.txn_type}</span>
              </td>
              <td className="px-4 py-2 text-right">{t.amount.toLocaleString()} {t.currency}</td>
              <td className="px-4 py-2">{t.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
