"use client";

import { api } from "@/lib/api-client";
const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { Button } from "@/components/ui/button";
import BarcodeScanner from "@/components/app/BarcodeScanner";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Barcode, Camera, Minus, Plus, ShoppingCart, Trash2, X } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Product {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  sell_price: string;
  tax_rate: string;
  unit: string;
  stock: number;
}

interface CartItem {
  product_id: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
}

interface Session {
  id: string;
  status: string;
  sale_count: number;
  total_revenue: string;
}

interface Sale {
  id: string;
  sale_number: string;
  total: string;
  payment_method: string;
  change_due: string | null;
  created_at: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number | string) {
  return Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function cartTotals(items: CartItem[]) {
  let subtotal = 0;
  let vat = 0;
  for (const item of items) {
    const line = item.quantity * item.unit_price;
    subtotal += line;
    vat += line * item.tax_rate / 100;
  }
  return { subtotal, vat, total: subtotal + vat };
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function PosPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [barcodeInput, setBarcodeInput] = useState("");
  const [payment, setPayment] = useState<"CASH" | "CARD" | "SWISH">("CASH");
  const [tendered, setTendered] = useState("");
  const [processing, setProcessing] = useState(false);
  const [lastSale, setLastSale] = useState<Sale | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const barcodeRef = useRef<HTMLInputElement>(null);

  // Open or resume session on mount
  useEffect(() => {
    api.post<Session>("/api/pos/sessions", {}).then(setSession).catch(console.error);
  }, []);

  // Load product grid
  useEffect(() => {
    const q = searchQ.trim();
    api.get<Product[]>(`/api/pos/products${q ? `?q=${encodeURIComponent(q)}` : ""}`)
      .then(setProducts)
      .catch(console.error);
  }, [searchQ]);

  // Handle barcode scan (Enter key in hidden barcode input)
  async function handleBarcodeScan(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const code = barcodeInput.trim();
    if (!code) return;
    setBarcodeInput("");
    try {
      const p = await api.get<Product>(`/api/pos/lookup?barcode=${encodeURIComponent(code)}`);
      addToCart(p);
    } catch {
      toast.error(`Barcode not found: ${code}`);
    }
  }

  function addToCart(p: Product) {
    setCart((prev) => {
      const existing = prev.findIndex((i) => i.product_id === p.id);
      if (existing >= 0) {
        return prev.map((item, idx) =>
          idx === existing ? { ...item, quantity: item.quantity + 1 } : item
        );
      }
      return [...prev, {
        product_id: p.id,
        description: p.name,
        quantity: 1,
        unit_price: Number(p.sell_price),
        tax_rate: Number(p.tax_rate),
      }];
    });
  }

  function updateQty(idx: number, delta: number) {
    setCart((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], quantity: Math.max(1, updated[idx].quantity + delta) };
      return updated;
    });
  }

  function removeItem(idx: number) {
    setCart((prev) => prev.filter((_, i) => i !== idx));
  }

  async function checkout() {
    if (!session || cart.length === 0) return;
    setProcessing(true);
    try {
      const sale = await api.post<Sale>("/api/pos/sales", {
        session_id: session.id,
        items: cart,
        payment_method: payment,
        amount_tendered: payment === "CASH" && tendered ? Number(tendered) : null,
      });
      setLastSale(sale);
      setCart([]);
      setTendered("");
      setSession((s) => s ? { ...s, sale_count: s.sale_count + 1 } : s);
      toast.success(`Sale ${sale.sale_number} complete`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setProcessing(false);
    }
  }

  async function closeSession() {
    if (!session || !confirm("Close the cash register session?")) return;
    try {
      await api.patch(`/api/pos/sessions/${session.id}/close`, {});
      setSession(null);
      setCart([]);
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  const { subtotal, vat, total } = cartTotals(cart);
  const change = payment === "CASH" && tendered ? Number(tendered) - total : null;

  async function handleCameraScan(code: string) {
    setCameraOpen(false);
    try {
      const p = await api.get<Product>(`/api/pos/lookup?barcode=${encodeURIComponent(code)}`);
      addToCart(p);
      toast.success(`Added: ${p.name}`);
    } catch {
      toast.error(`Barcode not found: ${code}`);
    }
  }

  return (
    <>
      {cameraOpen && (
        <BarcodeScanner onResult={handleCameraScan} onClose={() => setCameraOpen(false)} />
      )}
    <div className="flex h-[calc(100vh-6rem)] gap-4">
      {/* Left: product search + grid */}
      <div className="flex flex-1 flex-col gap-3 overflow-hidden">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Cash Register</h1>
          {session && (
            <div className="flex items-center gap-3 text-sm text-gray-500">
              <span>{session.sale_count} sales today</span>
              <Button variant="outline" size="sm" onClick={closeSession}>Close session</Button>
            </div>
          )}
        </div>

        {/* Barcode input (focus it for USB scanner) + camera button */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Barcode className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              ref={barcodeRef}
              value={barcodeInput}
              onChange={(e) => setBarcodeInput(e.target.value)}
              onKeyDown={handleBarcodeScan}
              placeholder="Scan barcode or type EAN…"
              className="w-full rounded-md border border-gray-300 pl-9 pr-3 py-2 text-sm focus:border-[#0f1724] focus:outline-none focus:ring-1 focus:ring-[#0f1724]"
            />
          </div>
          <button
            onClick={() => setCameraOpen(true)}
            title="Use camera to scan"
            className="flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <Camera className="h-4 w-4" />
            <span className="hidden sm:inline">Camera</span>
          </button>
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search products…"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#0f1724] focus:outline-none focus:ring-1 focus:ring-[#0f1724]"
          />
        </div>

        {/* Product grid */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-3 gap-3 pb-2">
            {products.map((p) => (
              <button
                key={p.id}
                onClick={() => addToCart(p)}
                className="flex flex-col items-start rounded-xl border bg-white p-3 text-left shadow-sm transition hover:border-[#1a2332] hover:shadow-md"
              >
                <span className="font-medium text-sm text-[#1a2332] line-clamp-2">{p.name}</span>
                <span className="mt-1 text-xs text-gray-500">{p.sku}</span>
                <div className="mt-2 flex w-full items-center justify-between">
                  <span className="text-sm font-bold text-[#1a2332]">{fmt(p.sell_price)} kr</span>
                  <span className={`text-xs ${p.stock <= 0 ? "text-red-500" : "text-gray-400"}`}>
                    {p.stock} {p.unit}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right: cart + checkout */}
      <div className="flex w-80 flex-col gap-3 rounded-xl border bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <ShoppingCart className="h-5 w-5 text-[#1a2332]" />
          <h2 className="font-semibold text-[#1a2332]">Cart</h2>
          {cart.length > 0 && (
            <button onClick={() => setCart([])} className="ml-auto text-xs text-gray-400 hover:text-red-500">
              Clear
            </button>
          )}
        </div>

        {/* Cart items */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {cart.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400">Add items by scanning or clicking products</p>
          )}
          {cart.map((item, idx) => (
            <div key={idx} className="flex items-start gap-2 rounded-lg border p-2">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-[#1a2332] truncate">{item.description}</p>
                <p className="text-xs text-gray-500">{fmt(item.unit_price)} kr × {item.quantity}</p>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => updateQty(idx, -1)} className="rounded p-0.5 hover:bg-gray-100">
                  <Minus className="h-3 w-3" />
                </button>
                <span className="w-5 text-center text-xs font-medium">{item.quantity}</span>
                <button onClick={() => updateQty(idx, 1)} className="rounded p-0.5 hover:bg-gray-100">
                  <Plus className="h-3 w-3" />
                </button>
                <button onClick={() => removeItem(idx)} className="ml-1 rounded p-0.5 hover:bg-red-50 text-red-400">
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Totals */}
        <div className="border-t pt-3 space-y-1 text-sm">
          <div className="flex justify-between text-gray-500">
            <span>Subtotal</span><span>{fmt(subtotal)} kr</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>VAT</span><span>{fmt(vat)} kr</span>
          </div>
          <div className="flex justify-between font-bold text-[#1a2332] text-base">
            <span>Total</span><span>{fmt(total)} kr</span>
          </div>
        </div>

        {/* Payment method */}
        <div className="flex gap-1 rounded-lg border p-1">
          {(["CASH", "CARD", "SWISH"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setPayment(m)}
              className={`flex-1 rounded py-1.5 text-xs font-medium transition ${
                payment === m ? "bg-[#1a2332] text-white" : "text-gray-500 hover:bg-gray-50"
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        {/* Cash tendered */}
        {payment === "CASH" && (
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Amount tendered (kr)</label>
            <input
              type="number"
              step="1"
              value={tendered}
              onChange={(e) => setTendered(e.target.value)}
              placeholder={fmt(Math.ceil(total / 10) * 10)}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
            {change !== null && change >= 0 && (
              <p className="text-sm font-semibold text-green-600">Change: {fmt(change)} kr</p>
            )}
          </div>
        )}



        <Button
          onClick={checkout}
          disabled={processing || cart.length === 0 || !session}
          className="w-full bg-[#0f1724] hover:bg-[#1a2840] text-white"
        >
          {processing ? "Processing…" : `Charge ${fmt(total)} kr`}
        </Button>

        {/* Last sale confirmation */}
        {lastSale && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-xs space-y-1">
            <p className="font-semibold text-green-700">Sale complete — {lastSale.sale_number}</p>
            {lastSale.change_due && Number(lastSale.change_due) > 0 && (
              <p className="text-green-600">Change: {fmt(lastSale.change_due)} kr</p>
            )}
            <button
              onClick={() => window.open(`${apiBase}/api/pos/sales/${lastSale.id}/receipt`, "_blank")}
              className="text-green-700 underline"
            >
              Print receipt
            </button>
          </div>
        )}
      </div>
    </div>
    </>
  );
}
