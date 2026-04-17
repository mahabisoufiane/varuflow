"use client";

import { api } from "@/lib/api-client";
const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { Button } from "@/components/ui/button";
import BarcodeScanner from "@/components/app/BarcodeScanner";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Barcode, Camera, ChevronDown, ChevronUp, Clock, Minus,
  Pause, Play, Plus, Printer, RotateCcw, Search, ShoppingCart,
  Tag, User, X, Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useMoney } from "@/hooks/useMoney";

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
  discount_pct: number; // 0–100
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
  subtotal: string;
  vat_amount: string;
  payment_method: string;
  change_due: string | null;
  is_refunded: boolean;
  created_at: string;
  items: { description: string; quantity: string; line_total: string }[];
}

interface Customer {
  id: string;
  company_name: string;
  email: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function lineTotal(item: CartItem) {
  const base = item.quantity * item.unit_price;
  return base * (1 - item.discount_pct / 100);
}

function cartTotals(items: CartItem[], saleDiscount: number) {
  let subtotal = 0;
  let vat = 0;
  for (const item of items) {
    const lt = lineTotal(item);
    subtotal += lt;
    vat += lt * item.tax_rate / 100;
  }
  const gross = subtotal + vat;
  const discountAmt = gross * (saleDiscount / 100);
  return { subtotal, vat, gross, discountAmt, total: gross - discountAmt };
}

const QUICK_CASH = [100, 200, 500, 1000];

// ── Main component ─────────────────────────────────────────────────────────────

export default function PosPage() {
  const { fmt: fmtMoney } = useMoney();
  const fmt = (n: number | string) => fmtMoney(Number(n), { decimals: 2 });
  const [session, setSession]             = useState<Session | null>(null);
  const [products, setProducts]           = useState<Product[]>([]);
  const [cart, setCart]                   = useState<CartItem[]>([]);
  const [heldCart, setHeldCart]           = useState<CartItem[] | null>(null);
  const [searchQ, setSearchQ]             = useState("");
  const [barcodeInput, setBarcodeInput]   = useState("");
  const [payment, setPayment]             = useState<"CASH" | "CARD" | "SWISH">("CASH");
  const [tendered, setTendered]           = useState("");
  const [saleDiscount, setSaleDiscount]   = useState(0); // % off total
  const [editDiscountOpen, setEditDiscountOpen] = useState(false);
  const [processing, setProcessing]       = useState(false);
  const [lastSale, setLastSale]           = useState<Sale | null>(null);
  const [recentSales, setRecentSales]     = useState<Sale[]>([]);
  const [showRecent, setShowRecent]       = useState(false);
  const [cameraOpen, setCameraOpen]       = useState(false);
  const [closingModal, setClosingModal]   = useState(false);
  const [scannerReady, setScannerReady]   = useState(false);
  const [editQtyIdx, setEditQtyIdx]       = useState<number | null>(null);
  const [editQtyVal, setEditQtyVal]       = useState("");
  const [customers, setCustomers]         = useState<Customer[]>([]);
  const [customerSearch, setCustomerSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [customerDropOpen, setCustomerDropOpen] = useState(false);
  const barcodeRef = useRef<HTMLInputElement>(null);

  // Open or resume session
  useEffect(() => {
    api.post<Session>("/api/pos/sessions", {}).then(setSession).catch(console.error);
  }, []);

  // Load product grid
  useEffect(() => {
    const q = searchQ.trim();
    api.get<Product[]>(`/api/pos/products${q ? `?q=${encodeURIComponent(q)}` : ""}`)
      .then(setProducts).catch(console.error);
  }, [searchQ]);

  // Load customers for selection
  useEffect(() => {
    api.get<Customer[]>(`/api/invoicing/customers${customerSearch ? `?search=${encodeURIComponent(customerSearch)}` : ""}`)
      .then(setCustomers).catch(() => {});
  }, [customerSearch]);

  // Load recent sales when session is set
  useEffect(() => {
    if (!session) return;
    api.get<Sale[]>(`/api/pos/sessions/${session.id}/sales`)
      .then(setRecentSales).catch(() => {});
  }, [session, lastSale]);

  // ── Global USB / BT barcode scanner listener ──────────────────────────────
  useEffect(() => {
    let buf = "";
    let lastAt = 0;
    setScannerReady(true);

    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      const isOtherInput =
        (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) &&
        target !== barcodeRef.current;
      if (isOtherInput) return;

      const now = Date.now();
      if (e.key === "Enter") {
        const code = buf.trim();
        buf = "";
        if (code.length >= 3) {
          setBarcodeInput(code);
          setTimeout(() => {
            barcodeRef.current?.dispatchEvent(
              new KeyboardEvent("keydown", { key: "Enter", bubbles: true })
            );
          }, 0);
        }
        return;
      }
      if (now - lastAt > 80) buf = "";
      lastAt = now;
      if (e.key.length === 1) {
        buf += e.key;
        if (now - lastAt <= 80 && target !== barcodeRef.current) e.preventDefault();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      setScannerReady(false);
    };
  }, []);

  // ── Barcode / lookup ─────────────────────────────────────────────────────

  async function handleBarcodeScan(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    const code = barcodeInput.trim();
    if (!code) return;
    setBarcodeInput("");
    try {
      const p = await api.get<Product>(`/api/pos/lookup?barcode=${encodeURIComponent(code)}`);
      addToCart(p);
      toast.success(`Added: ${p.name}`);
    } catch {
      toast.error(`Barcode not found: ${code}`);
    }
    setTimeout(() => barcodeRef.current?.focus(), 50);
  }

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

  // ── Cart operations ──────────────────────────────────────────────────────

  function addToCart(p: Product) {
    setCart((prev) => {
      const idx = prev.findIndex((i) => i.product_id === p.id);
      if (idx >= 0) {
        return prev.map((item, i) =>
          i === idx ? { ...item, quantity: item.quantity + 1 } : item
        );
      }
      return [...prev, {
        product_id: p.id,
        description: p.name,
        quantity: 1,
        unit_price: Number(p.sell_price),
        tax_rate: Number(p.tax_rate),
        discount_pct: 0,
      }];
    });
  }

  function updateQty(idx: number, delta: number) {
    setCart((prev) =>
      prev.map((item, i) =>
        i === idx ? { ...item, quantity: Math.max(1, item.quantity + delta) } : item
      )
    );
  }

  function commitQtyEdit(idx: number) {
    const n = parseInt(editQtyVal, 10);
    if (!isNaN(n) && n > 0) {
      setCart((prev) =>
        prev.map((item, i) => (i === idx ? { ...item, quantity: n } : item))
      );
    }
    setEditQtyIdx(null);
    setEditQtyVal("");
  }

  function updateItemDiscount(idx: number, pct: number) {
    setCart((prev) =>
      prev.map((item, i) =>
        i === idx ? { ...item, discount_pct: Math.min(100, Math.max(0, pct)) } : item
      )
    );
  }

  function removeItem(idx: number) {
    setCart((prev) => prev.filter((_, i) => i !== idx));
  }

  // ── Hold / resume ────────────────────────────────────────────────────────

  function holdSale() {
    if (cart.length === 0) return;
    setHeldCart(cart);
    setCart([]);
    toast("Sale held — tap Resume to bring it back");
  }

  function resumeSale() {
    if (!heldCart) return;
    setCart(heldCart);
    setHeldCart(null);
  }

  // ── Checkout ─────────────────────────────────────────────────────────────

  async function checkout() {
    if (!session || cart.length === 0) return;
    setProcessing(true);
    try {
      const { total } = cartTotals(cart, saleDiscount);
      // Apply sale-level discount by proportionally reducing each unit_price
      const factor = 1 - saleDiscount / 100;
      const apiItems = cart.map((item) => ({
        product_id: item.product_id,
        description: item.description,
        quantity: item.quantity,
        unit_price: Number((item.unit_price * (1 - item.discount_pct / 100) * factor).toFixed(4)),
        tax_rate: item.tax_rate,
      }));

      const sale = await api.post<Sale>("/api/pos/sales", {
        session_id: session.id,
        items: apiItems,
        payment_method: payment,
        amount_tendered: payment === "CASH" && tendered ? Number(tendered) : null,
        customer_id: selectedCustomer?.id ?? null,
      });

      setLastSale(sale);
      setCart([]);
      setTendered("");
      setSaleDiscount(0);
      setSession((s) => s ? { ...s, sale_count: s.sale_count + 1 } : s);
      toast.success(`Sale ${sale.sale_number} — ${fmt(sale.total)}`);
    } catch (e: any) {
      toast.error(e.message ?? "Checkout failed");
    } finally {
      setProcessing(false);
    }
  }

  // ── Refund ────────────────────────────────────────────────────────────────

  async function refundSale(saleId: string) {
    if (!confirm("Refund this sale and restore stock?")) return;
    try {
      await api.post(`/api/pos/sales/${saleId}/refund`, {});
      setRecentSales((prev) => prev.map((s) => s.id === saleId ? { ...s, is_refunded: true } : s));
      toast.success("Sale refunded and stock restored");
    } catch (e: any) {
      toast.error(e.message ?? "Refund failed");
    }
  }

  // ── Close session ─────────────────────────────────────────────────────────

  async function closeSession() {
    if (!session) return;
    setClosingModal(false);
    try {
      await api.patch(`/api/pos/sessions/${session.id}/close`, {});
      setSession(null);
      setCart([]);
      toast.success("Session closed");
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────

  const { subtotal, vat, gross, discountAmt, total } = cartTotals(cart, saleDiscount);
  const change = payment === "CASH" && tendered ? Number(tendered) - total : null;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {cameraOpen && <BarcodeScanner onResult={handleCameraScan} onClose={() => setCameraOpen(false)} />}

      {/* ── Session close confirmation modal ── */}
      {closingModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setClosingModal(false)} />
          <div className="relative bg-white rounded-2xl p-6 shadow-xl w-80 space-y-4">
            <h3 className="font-semibold text-gray-900">Close session?</h3>
            <div className="rounded-lg bg-gray-50 p-3 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Sales today</span>
                <span className="font-medium">{session?.sale_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total revenue</span>
                <span className="font-medium">{fmt(session?.total_revenue ?? 0)}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setClosingModal(false)} className="flex-1 rounded-lg border px-3 py-2 text-sm text-gray-600 hover:bg-gray-50">
                Cancel
              </button>
              <button onClick={closeSession} className="flex-1 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700">
                Close session
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex h-[calc(100vh-6rem)] gap-4">

        {/* ── Left: search + product grid ─────────────────────────────── */}
        <div className="flex flex-1 flex-col gap-3 overflow-hidden">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Cash Register</h1>
              {session && (
                <p className="text-xs text-gray-400">
                  {session.sale_count} sales · {fmt(session.total_revenue)}today
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {heldCart && (
                <button
                  onClick={resumeSale}
                  className="flex items-center gap-1.5 rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
                >
                  <Play className="h-3 w-3" /> Resume held sale
                </button>
              )}
              <button
                onClick={() => setShowRecent(!showRecent)}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
              >
                <Clock className="h-3 w-3" />
                Recent
              </button>
              {session && (
                <button
                  onClick={() => setClosingModal(true)}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
                >
                  Close session
                </button>
              )}
            </div>
          </div>

          {/* Recent sales panel */}
          {showRecent && (
            <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 border-b">
                <p className="text-xs font-semibold text-gray-700">Recent sales this session</p>
                <button onClick={() => setShowRecent(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              {session && (
                <div className="px-4 py-2 border-b bg-gray-50 flex items-center justify-between">
                  <span className="text-[10px] text-gray-400">Z-report</span>
                  <button
                    onClick={() => window.open(`${apiBase}/api/pos/sessions/${session.id}/zreport`, "_blank")}
                    className="flex items-center gap-1 text-[10px] text-[#1a2332] hover:underline font-medium"
                  >
                    <Printer className="h-3 w-3" /> Download PDF
                  </button>
                </div>
              )}
              {recentSales.length === 0 ? (
                <p className="px-4 py-3 text-xs text-gray-400">No sales yet</p>
              ) : (
                <div className="divide-y max-h-48 overflow-y-auto">
                  {recentSales.slice(0, 10).map((s) => (
                    <div key={s.id} className={cn("flex items-center justify-between px-4 py-2", s.is_refunded && "opacity-50")}>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <p className="text-xs font-medium text-gray-800">{s.sale_number}</p>
                          {s.is_refunded && (
                            <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-[9px] font-medium text-red-500">REFUNDED</span>
                          )}
                        </div>
                        <p className="text-[10px] text-gray-400">
                          {s.payment_method} · {new Date(s.created_at).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-semibold text-gray-900">{fmt(s.total)}</span>
                        <button
                          onClick={() => window.open(`${apiBase}/api/pos/sales/${s.id}/receipt`, "_blank")}
                          className="rounded p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                          title="Print receipt"
                        >
                          <Printer className="h-3 w-3" />
                        </button>
                        {!s.is_refunded && (
                          <button
                            onClick={() => refundSale(s.id)}
                            className="rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50"
                            title="Refund sale"
                          >
                            <RotateCcw className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Barcode + search inputs */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Barcode className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                ref={barcodeRef}
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={handleBarcodeScan}
                placeholder="Scan barcode or type EAN…"
                autoFocus
                className="w-full rounded-md border border-gray-300 pl-9 pr-28 py-2 text-sm focus:border-[#0f1724] focus:outline-none focus:ring-1 focus:ring-[#0f1724]"
              />
              {scannerReady && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 text-[10px] font-medium text-emerald-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Scanner ready
                </span>
              )}
            </div>
            <button
              onClick={() => setCameraOpen(true)}
              title="Use camera to scan"
              className="flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              <Camera className="h-4 w-4" />
              <span className="hidden sm:inline text-xs">Camera</span>
            </button>
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder="Search products…"
                className="w-full rounded-md border border-gray-300 pl-9 pr-3 py-2 text-sm focus:border-[#0f1724] focus:outline-none focus:ring-1 focus:ring-[#0f1724]"
              />
            </div>
          </div>

          {/* Product grid */}
          <div className="flex-1 overflow-y-auto">
            <div className="grid grid-cols-3 gap-2.5 pb-2">
              {products.map((p) => (
                <button
                  key={p.id}
                  onClick={() => addToCart(p)}
                  className="flex flex-col items-start rounded-xl border bg-white p-3 text-left shadow-sm transition hover:border-[#1a2332] hover:shadow-md active:scale-[0.98]"
                >
                  <span className="font-medium text-sm text-[#1a2332] line-clamp-2 leading-tight">{p.name}</span>
                  <span className="mt-0.5 text-[10px] text-gray-400">{p.sku}</span>
                  {p.barcode && (
                    <span className="mt-0.5 text-[10px] text-gray-300 font-mono">{p.barcode}</span>
                  )}
                  <div className="mt-2 flex w-full items-center justify-between">
                    <span className="text-sm font-bold text-[#1a2332]">{fmt(p.sell_price)}</span>
                    <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full font-medium",
                      p.stock <= 0 ? "bg-red-50 text-red-500" :
                      p.stock < 5 ? "bg-amber-50 text-amber-600" :
                      "bg-gray-50 text-gray-400"
                    )}>
                      {p.stock} {p.unit}
                    </span>
                  </div>
                </button>
              ))}
              {products.length === 0 && (
                <div className="col-span-3 py-12 text-center text-sm text-gray-400">
                  No products found
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Right: cart + checkout ──────────────────────────────────── */}
        <div className="flex w-[320px] flex-col gap-2 rounded-xl border bg-white p-4 shadow-sm">

          {/* Cart header */}
          <div className="flex items-center gap-2">
            <ShoppingCart className="h-4 w-4 text-[#1a2332]" />
            <h2 className="font-semibold text-sm text-[#1a2332]">Cart</h2>
            <span className="ml-1 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
              {cart.reduce((a, i) => a + i.quantity, 0)} items
            </span>
            <div className="ml-auto flex gap-1">
              {cart.length > 0 && (
                <>
                  <button
                    onClick={holdSale}
                    title="Hold sale"
                    className="rounded p-1 text-gray-400 hover:text-amber-600 hover:bg-amber-50"
                  >
                    <Pause className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => { setCart([]); setSaleDiscount(0); }}
                    title="Clear cart"
                    className="rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Cart items */}
          <div className="flex-1 overflow-y-auto space-y-1.5 min-h-0">
            {cart.length === 0 && (
              <div className="py-8 text-center text-xs text-gray-400 space-y-1">
                <ShoppingCart className="mx-auto h-8 w-8 text-gray-200" />
                <p>Scan a product or click from the grid</p>
              </div>
            )}

            {cart.map((item, idx) => (
              <div key={idx} className="rounded-lg border border-gray-100 bg-gray-50 p-2 space-y-1.5">
                <div className="flex items-start justify-between gap-1">
                  <p className="text-xs font-medium text-[#1a2332] leading-tight flex-1 truncate">{item.description}</p>
                  <button onClick={() => removeItem(idx)} className="shrink-0 rounded p-0.5 text-gray-300 hover:text-red-400">
                    <X className="h-3 w-3" />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  {/* Qty control */}
                  <div className="flex items-center gap-1">
                    <button onClick={() => updateQty(idx, -1)} className="rounded bg-white border h-6 w-6 flex items-center justify-center hover:bg-gray-100">
                      <Minus className="h-2.5 w-2.5" />
                    </button>
                    {editQtyIdx === idx ? (
                      <input
                        type="number"
                        className="w-10 rounded border text-center text-xs py-0.5"
                        value={editQtyVal}
                        onChange={(e) => setEditQtyVal(e.target.value)}
                        onBlur={() => commitQtyEdit(idx)}
                        onKeyDown={(e) => { if (e.key === "Enter") commitQtyEdit(idx); if (e.key === "Escape") { setEditQtyIdx(null); } }}
                        autoFocus
                      />
                    ) : (
                      <button
                        className="w-8 text-center text-xs font-semibold text-gray-700 hover:bg-white rounded border border-transparent hover:border-gray-200"
                        onClick={() => { setEditQtyIdx(idx); setEditQtyVal(String(item.quantity)); }}
                        title="Click to edit quantity"
                      >
                        {item.quantity}
                      </button>
                    )}
                    <button onClick={() => updateQty(idx, 1)} className="rounded bg-white border h-6 w-6 flex items-center justify-center hover:bg-gray-100">
                      <Plus className="h-2.5 w-2.5" />
                    </button>
                  </div>

                  {/* Price + discount */}
                  <div className="flex items-center gap-2">
                    {item.discount_pct > 0 && (
                      <span className="text-[10px] text-red-500 font-medium">-{item.discount_pct}%</span>
                    )}
                    <span className="text-xs font-semibold text-gray-700">{fmt(lineTotal(item))}</span>
                  </div>
                </div>

                {/* Per-item discount */}
                <div className="flex items-center gap-1">
                  <Tag className="h-2.5 w-2.5 text-gray-300" />
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={5}
                    value={item.discount_pct || ""}
                    onChange={(e) => updateItemDiscount(idx, Number(e.target.value))}
                    placeholder="0% disc"
                    className="w-20 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] text-gray-600 focus:outline-none focus:border-gray-400"
                  />
                  <span className="text-[10px] text-gray-400">
                    {fmt(item.unit_price)} × {item.quantity}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Customer selection */}
          <div className="relative">
            <div
              className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1.5 cursor-pointer hover:bg-gray-100"
              onClick={() => setCustomerDropOpen(!customerDropOpen)}
            >
              <User className="h-3.5 w-3.5 text-gray-400 shrink-0" />
              <span className="text-xs text-gray-600 flex-1 truncate">
                {selectedCustomer ? selectedCustomer.company_name : "Walk-in customer"}
              </span>
              {selectedCustomer && (
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedCustomer(null); setCustomerSearch(""); }}
                  className="text-gray-300 hover:text-gray-500"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
            {customerDropOpen && (
              <div className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border bg-white shadow-lg">
                <div className="p-2">
                  <input
                    autoFocus
                    value={customerSearch}
                    onChange={(e) => setCustomerSearch(e.target.value)}
                    placeholder="Search customer…"
                    className="w-full rounded border border-gray-200 px-2 py-1 text-xs focus:outline-none focus:border-gray-400"
                  />
                </div>
                <div className="max-h-36 overflow-y-auto divide-y">
                  {customers.slice(0, 8).map((c) => (
                    <button
                      key={c.id}
                      onClick={() => { setSelectedCustomer(c); setCustomerDropOpen(false); setCustomerSearch(""); }}
                      className="w-full px-3 py-1.5 text-left hover:bg-gray-50"
                    >
                      <p className="text-xs font-medium text-gray-800">{c.company_name}</p>
                      {c.email && <p className="text-[10px] text-gray-400">{c.email}</p>}
                    </button>
                  ))}
                  {customers.length === 0 && (
                    <p className="px-3 py-2 text-xs text-gray-400">No customers found</p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Totals */}
          {cart.length > 0 && (
            <div className="border-t pt-2 space-y-0.5 text-xs">
              <div className="flex justify-between text-gray-400">
                <span>Subtotal</span><span>{fmt(subtotal)}</span>
              </div>
              <div className="flex justify-between text-gray-400">
                <span>VAT</span><span>{fmt(vat)}</span>
              </div>

              {/* Sale-level discount */}
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setEditDiscountOpen(!editDiscountOpen)}
                  className="flex items-center gap-1 text-gray-400 hover:text-gray-700"
                >
                  <Tag className="h-3 w-3" />
                  <span>Order discount</span>
                  {editDiscountOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
                {saleDiscount > 0 && (
                  <span className="text-red-500 font-medium">-{fmt(discountAmt)}</span>
                )}
              </div>
              {editDiscountOpen && (
                <div className="flex items-center gap-2 py-1">
                  {[5, 10, 15, 20].map((p) => (
                    <button
                      key={p}
                      onClick={() => setSaleDiscount(saleDiscount === p ? 0 : p)}
                      className={cn(
                        "flex-1 rounded border py-0.5 text-[10px] font-medium transition",
                        saleDiscount === p ? "bg-[#1a2332] border-[#1a2332] text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                      )}
                    >
                      {p}%
                    </button>
                  ))}
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={saleDiscount || ""}
                    onChange={(e) => setSaleDiscount(Number(e.target.value))}
                    placeholder="%"
                    className="w-12 rounded border px-1.5 py-0.5 text-[10px] text-center focus:outline-none focus:border-gray-400"
                  />
                </div>
              )}

              <div className="flex justify-between font-bold text-[#1a2332] text-sm pt-1 border-t">
                <span>Total</span><span>{fmt(total)}</span>
              </div>
            </div>
          )}

          {/* Payment method */}
          <div className="flex gap-1 rounded-lg border p-1">
            {(["CASH", "CARD", "SWISH"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setPayment(m)}
                className={cn(
                  "flex-1 rounded py-1.5 text-xs font-medium transition",
                  payment === m ? "bg-[#1a2332] text-white" : "text-gray-500 hover:bg-gray-50"
                )}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Cash tendered */}
          {payment === "CASH" && (
            <div className="space-y-1.5">
              <div className="flex gap-1">
                {QUICK_CASH.map((amt) => (
                  <button
                    key={amt}
                    onClick={() => setTendered(String(amt))}
                    className={cn(
                      "flex-1 rounded border py-1 text-[10px] font-medium transition",
                      Number(tendered) === amt ? "bg-[#1a2332] border-[#1a2332] text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                    )}
                  >
                    {amt}
                  </button>
                ))}
              </div>
              <input
                type="number"
                step="1"
                value={tendered}
                onChange={(e) => setTendered(e.target.value)}
                placeholder={`Tendered (min ${fmt(Math.ceil(total / 10) * 10)})`}
                className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
              {change !== null && change >= 0 && (
                <p className="text-center text-sm font-bold text-green-600">Change: {fmt(change)}</p>
              )}
              {change !== null && change < 0 && (
                <p className="text-center text-xs text-red-500">Insufficient amount</p>
              )}
            </div>
          )}

          {/* Checkout */}
          <Button
            onClick={checkout}
            disabled={
              processing || cart.length === 0 || !session ||
              (payment === "CASH" && !!tendered && Number(tendered) < total)
            }
            className="w-full bg-[#0f1724] hover:bg-[#1a2840] text-white font-semibold"
          >
            {processing ? "Processing…" : `Charge ${fmt(total)}`}
          </Button>

          {/* Last sale receipt */}
          {lastSale && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-xs space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="font-semibold text-green-700">{lastSale.sale_number} — {fmt(lastSale.total)}</p>
                <button onClick={() => setLastSale(null)} className="text-green-400 hover:text-green-600">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              {lastSale.change_due && Number(lastSale.change_due) > 0 && (
                <p className="text-green-600 font-medium">Change: {fmt(lastSale.change_due)}</p>
              )}
              <button
                onClick={() => window.open(`${apiBase}/api/pos/sales/${lastSale.id}/receipt`, "_blank")}
                className="flex items-center gap-1.5 text-green-700 font-medium hover:underline"
              >
                <Printer className="h-3 w-3" /> Print receipt
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
