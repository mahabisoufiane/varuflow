"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

interface LineItem { description: string; quantity: string; unit_price: string; }

export default function NewQuotePage() {
  const router = useRouter();
  const [form, setForm] = useState({ customer_id: "", title: "", quote_number: "", cover_text: "", scope: "", terms: "", valid_until: "", currency: "SEK" });
  const [items, setItems] = useState<LineItem[]>([{ description: "", quantity: "1", unit_price: "" }]);

  const addItem = () => setItems([...items, { description: "", quantity: "1", unit_price: "" }]);
  const updateItem = (i: number, field: string, val: string) => { const n = [...items]; (n[i] as any)[field] = val; setItems(n); };
  const removeItem = (i: number) => setItems(items.filter((_, idx) => idx !== i));

  const submit = async () => {
    const body = {
      ...form,
      valid_until: form.valid_until || null,
      items: items.filter(i => i.description).map(i => ({ description: i.description, quantity: parseFloat(i.quantity) || 1, unit_price: parseFloat(i.unit_price) || 0 })),
    };
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/quotes`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "include", body: JSON.stringify(body),
    });
    if (res.ok) { const data = await res.json(); router.push(`/quotes/${data.id}`); }
  };

  return (
    <div className="p-6 max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold">Create Quote</h1>
      <div className="space-y-3 bg-white border rounded p-4">
        <input placeholder="Customer ID" value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value })} className="w-full border rounded px-3 py-2" />
        <input placeholder="Title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} className="w-full border rounded px-3 py-2" />
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Quote Number (optional)" value={form.quote_number} onChange={e => setForm({ ...form, quote_number: e.target.value })} className="border rounded px-3 py-2" />
          <input type="date" placeholder="Valid until" value={form.valid_until} onChange={e => setForm({ ...form, valid_until: e.target.value })} className="border rounded px-3 py-2" />
        </div>
        <textarea placeholder="Cover text (intro for client)" value={form.cover_text} onChange={e => setForm({ ...form, cover_text: e.target.value })} className="w-full border rounded px-3 py-2 h-20" />
        <textarea placeholder="Scope of work" value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })} className="w-full border rounded px-3 py-2 h-20" />
        <textarea placeholder="Terms & conditions" value={form.terms} onChange={e => setForm({ ...form, terms: e.target.value })} className="w-full border rounded px-3 py-2 h-20" />
      </div>

      <div className="bg-white border rounded p-4 space-y-2">
        <h2 className="font-bold">Line Items</h2>
        {items.map((item, i) => (
          <div key={i} className="flex gap-2">
            <input placeholder="Description" value={item.description} onChange={e => updateItem(i, "description", e.target.value)} className="flex-1 border rounded px-3 py-2" />
            <input placeholder="Qty" value={item.quantity} onChange={e => updateItem(i, "quantity", e.target.value)} className="w-20 border rounded px-3 py-2" />
            <input placeholder="Price" value={item.unit_price} onChange={e => updateItem(i, "unit_price", e.target.value)} className="w-28 border rounded px-3 py-2" />
            <button onClick={() => removeItem(i)} className="text-red-500 px-2">×</button>
          </div>
        ))}
        <button onClick={addItem} className="text-blue-600 text-sm">+ Add line</button>
      </div>

      <button onClick={submit} className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Create Quote</button>
    </div>
  );
}
