"use client";

// Full-screen cash register. Backed entirely by the existing /api/pos API:
// sessions (open register), products grid, barcode lookup, idempotent sales,
// PDF receipts. Hardware scanners work globally via useBarcodeListener
// (keyboard-wedge, <60ms keystroke gap + Enter); camera scanning via the
// shared BarcodeScanner (native BarcodeDetector → zxing fallback).
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Banknote, Camera, CheckCircle2, CreditCard, Loader2, Minus, Plus,
  Printer, ScanLine, Search, Smartphone, Trash2, X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { useBarcodeListener } from "@/components/barcode/useBarcodeListener";

const BarcodeScanner = dynamic(() => import("@/components/app/BarcodeScanner"), { ssr: false });

interface PosProduct {
  id: string; name: string; sku: string; barcode: string | null;
  sell_price: string; tax_rate: string; unit: string; stock: number;
  image_url: string | null;
}
interface PosSession {
  id: string; status: string; opened_at: string;
  sale_count: number; total_revenue: string;
}
interface SaleOut {
  id: string; sale_number: string; subtotal: string; vat_amount: string;
  total: string; change_due: string | null;
}
interface CartLine { product: PosProduct; qty: number }

const SEK = new Intl.NumberFormat("sv-SE", { style: "currency", currency: "SEK" });
const fmt = (n: number) => SEK.format(n);

// Deterministic tile art for products without a photo: a fixed set of
// Nordic-muted gradients keyed by name hash + the product's initials.
const TILE_HUES = [212, 158, 32, 262, 190, 350, 96, 18, 280, 140];
function tileStyle(name: string) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const hue = TILE_HUES[h % TILE_HUES.length];
  return {
    background: `linear-gradient(135deg, hsl(${hue} 32% 30%), hsl(${hue} 40% 18%))`,
  };
}
function initials(name: string) {
  return name.split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

export default function PosPage() {
  const t = useTranslations("pos");
  const [session, setSession] = useState<PosSession | null>(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);
  const [opening, setOpening] = useState(false);
  const [products, setProducts] = useState<PosProduct[]>([]);
  const [q, setQ] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [payMode, setPayMode] = useState<"CASH" | "CARD" | "SWISH" | null>(null);
  const [tendered, setTendered] = useState("");
  const [paying, setPaying] = useState(false);
  const [sale, setSale] = useState<SaleOut | null>(null);
  const [toast, setToast] = useState<{ text: string; kind: "ok" | "err" } | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioCtx = useRef<AudioContext | null>(null);

  // ── Audio feedback: short beep on scan, low buzz on unknown code ──
  const tone = useCallback((freq: number, ms: number) => {
    try {
      audioCtx.current ??= new AudioContext();
      const ctx = audioCtx.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + ms / 1000);
    } catch { /* audio unavailable (e.g. headless) — non-essential */ }
  }, []);

  const flash = useCallback((text: string, kind: "ok" | "err") => {
    setToast({ text, kind });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 1800);
  }, []);

  // ── Session ──
  useEffect(() => {
    api.get<PosSession[]>("/api/pos/sessions")
      .then((rows) => setSession(rows.find((s) => s.status === "OPEN") ?? null))
      .catch(() => setSession(null))
      .finally(() => setSessionLoaded(true));
  }, []);

  const openRegister = async () => {
    setOpening(true);
    try {
      setSession(await api.post<PosSession>("/api/pos/sessions", {}));
    } catch {
      flash(t("openTitle"), "err");
    } finally {
      setOpening(false);
    }
  };

  // ── Products (debounced server-side search) ──
  useEffect(() => {
    const h = setTimeout(() => {
      const url = q ? `/api/pos/products?q=${encodeURIComponent(q)}` : "/api/pos/products";
      api.get<PosProduct[]>(url).then(setProducts).catch(() => {});
    }, 250);
    return () => clearTimeout(h);
  }, [q]);

  // ── Cart ──
  const add = useCallback((p: PosProduct) => {
    setCart((c) => {
      const i = c.findIndex((l) => l.product.id === p.id);
      if (i >= 0) {
        const next = [...c];
        next[i] = { ...next[i], qty: next[i].qty + 1 };
        return next;
      }
      return [...c, { product: p, qty: 1 }];
    });
  }, []);
  const setQty = (id: string, qty: number) =>
    setCart((c) => (qty <= 0 ? c.filter((l) => l.product.id !== id)
      : c.map((l) => (l.product.id === id ? { ...l, qty } : l))));

  const totals = useMemo(() => {
    let sub = 0, vat = 0;
    for (const { product, qty } of cart) {
      const line = qty * parseFloat(product.sell_price);
      sub += line;
      vat += line * (parseFloat(product.tax_rate) / 100);
    }
    return { sub, vat, total: sub + vat };
  }, [cart]);

  // ── Scanning (hardware wedge — global; camera — overlay) ──
  const scan = useCallback(async (code: string) => {
    try {
      const p = await api.get<PosProduct>(`/api/pos/lookup?barcode=${encodeURIComponent(code)}`);
      add(p); tone(880, 90); flash(`${p.name} ${t("added")}`, "ok");
    } catch {
      try {
        const p = await api.get<PosProduct>(`/api/pos/lookup?sku=${encodeURIComponent(code)}`);
        add(p); tone(880, 90); flash(`${p.name} ${t("added")}`, "ok");
      } catch {
        tone(196, 220); flash(`${t("unknownBarcode")}: ${code}`, "err");
      }
    }
  }, [add, tone, flash, t]);

  useBarcodeListener({ onScan: scan, enabled: !!session && !sale && !cameraOpen });

  // ── Payment ──
  const tenderedNum = parseFloat(tendered.replace(",", ".")) || 0;
  const changeDue = tenderedNum - totals.total;
  const canPay = payMode === "CASH" ? tenderedNum >= totals.total - 0.001 : payMode !== null;

  const completeSale = async () => {
    if (!session || !payMode || cart.length === 0) return;
    setPaying(true);
    try {
      const result = await api.post<SaleOut>("/api/pos/sales", {
        session_id: session.id,
        items: cart.map(({ product, qty }) => ({
          product_id: product.id,
          description: product.name,
          quantity: qty,
          unit_price: parseFloat(product.sell_price),
          tax_rate: parseFloat(product.tax_rate),
        })),
        payment_method: payMode,
        amount_tendered: payMode === "CASH" ? tenderedNum : undefined,
        offline_id: crypto.randomUUID(),
      });
      setSale(result);
      tone(1174, 140);
    } catch {
      flash(t("insufficient"), "err");
    } finally {
      setPaying(false);
    }
  };

  const newSale = () => {
    setSale(null); setCart([]); setPayMode(null); setTendered(""); setQ("");
  };

  // ── Screens ──
  if (!sessionLoaded) {
    return (
      <div className="flex h-[100dvh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--vf-text-muted)]" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-[100dvh] items-center justify-center p-6" style={{ background: "var(--vf-bg-primary)" }}>
        <div className="w-full max-w-sm rounded-2xl border p-8 text-center space-y-5"
          style={{ background: "var(--vf-bg-surface)", borderColor: "var(--vf-border)" }}>
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full"
            style={{ background: "var(--vf-brand-primary-subtle)" }}>
            <ScanLine className="h-7 w-7" style={{ color: "var(--vf-brand-primary)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold vf-text-1">{t("openTitle")}</h1>
            <p className="mt-2 text-sm vf-text-2">{t("openBody")}</p>
          </div>
          <button onClick={openRegister} disabled={opening}
            className="vf-btn w-full justify-center text-base py-3">
            {opening ? <Loader2 className="h-5 w-5 animate-spin" /> : t("openBtn")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] flex-col" style={{ background: "var(--vf-bg-primary)" }}>
      {/* ── Top bar ── */}
      <header className="flex items-center gap-3 border-b px-4 py-2.5"
        style={{ borderColor: "var(--vf-border)", background: "var(--vf-bg-surface)" }}>
        <h1 className="text-base font-bold vf-text-1">{t("title")}</h1>
        <span className="hidden sm:flex items-center gap-1.5 text-xs vf-text-3">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          {t("scanReady")}
        </span>
        <div className="relative ml-auto w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 vf-text-3" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")}
            className="vf-input w-full pl-9 py-2 text-sm" />
        </div>
        <button onClick={() => setCameraOpen(true)} title={t("camera")}
          className="vf-btn-secondary flex items-center gap-2 px-3 py-2 text-sm shrink-0">
          <Camera className="h-4 w-4" /><span className="hidden md:inline">{t("camera")}</span>
        </button>
        <span className="hidden lg:block text-xs vf-text-3 shrink-0">
          {session.sale_count} {t("sales")} · {fmt(parseFloat(session.total_revenue))}
        </span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* ── Product grid ── */}
        <main className="flex-1 overflow-y-auto p-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {products.map((p) => (
              <button key={p.id} onClick={() => { add(p); tone(880, 60); }}
                className="group overflow-hidden rounded-xl border text-left transition-transform active:scale-[0.97]"
                style={{ background: "var(--vf-bg-surface)", borderColor: "var(--vf-border)" }}>
                <div className="relative aspect-square w-full overflow-hidden">
                  {p.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.image_url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center" style={tileStyle(p.name)}>
                      <span className="text-3xl font-bold text-white/80">{initials(p.name)}</span>
                    </div>
                  )}
                  {p.stock <= 5 && (
                    <span className="absolute left-2 top-2 rounded-full bg-amber-500/90 px-2 py-0.5 text-xs font-semibold text-black">
                      {t("stockLeft")} · {p.stock}
                    </span>
                  )}
                </div>
                <div className="p-2.5">
                  <p className="truncate text-sm font-medium vf-text-1">{p.name}</p>
                  <p className="mt-0.5 text-sm font-semibold" style={{ color: "var(--vf-brand-primary)" }}>
                    {fmt(parseFloat(p.sell_price))}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </main>

        {/* ── Cart ── */}
        <aside className="flex w-[340px] lg:w-[380px] shrink-0 flex-col border-l"
          style={{ borderColor: "var(--vf-border)", background: "var(--vf-bg-surface)" }}>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {cart.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
                <ScanLine className="h-8 w-8 vf-text-3" />
                <p className="text-sm font-medium vf-text-2">{t("emptyCart")}</p>
                <p className="text-xs vf-text-3">{t("emptyCartHint")}</p>
              </div>
            )}
            {cart.map(({ product, qty }) => (
              <div key={product.id} className="flex items-center gap-2 rounded-lg border p-2"
                style={{ borderColor: "var(--vf-border)", background: "var(--vf-bg-primary)" }}>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium vf-text-1">{product.name}</p>
                  <p className="text-xs vf-text-3">{fmt(parseFloat(product.sell_price))} / {product.unit}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setQty(product.id, qty - 1)} className="vf-btn-secondary h-8 w-8 p-0 flex items-center justify-center rounded-md">
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <span className="w-8 text-center text-sm font-semibold vf-text-1">{qty}</span>
                  <button onClick={() => setQty(product.id, qty + 1)} className="vf-btn-secondary h-8 w-8 p-0 flex items-center justify-center rounded-md">
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
                <p className="w-20 text-right text-sm font-semibold vf-text-1">
                  {fmt(qty * parseFloat(product.sell_price))}
                </p>
                <button onClick={() => setQty(product.id, 0)} className="vf-text-3 hover:text-red-500">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          {/* Totals + payment */}
          <div className="border-t p-3 space-y-3" style={{ borderColor: "var(--vf-border)" }}>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between vf-text-2"><span>{t("subtotal")}</span><span>{fmt(totals.sub)}</span></div>
              <div className="flex justify-between vf-text-2"><span>{t("vat")}</span><span>{fmt(totals.vat)}</span></div>
              <div className="flex justify-between text-lg font-bold vf-text-1"><span>{t("total")}</span><span>{fmt(totals.total)}</span></div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {([["CASH", Banknote, t("cash")], ["CARD", CreditCard, t("card")], ["SWISH", Smartphone, t("swish")]] as const)
                .map(([mode, Icon, label]) => (
                <button key={mode} onClick={() => setPayMode(mode)}
                  className="flex flex-col items-center gap-1 rounded-lg border py-2.5 text-xs font-semibold transition-colors"
                  style={payMode === mode
                    ? { background: "var(--vf-brand-primary)", borderColor: "var(--vf-brand-primary)", color: "var(--vf-brand-text-on-primary)" }
                    : { borderColor: "var(--vf-border)", color: "var(--vf-text-secondary)" }}>
                  <Icon className="h-5 w-5" />{label}
                </button>
              ))}
            </div>

            {payMode === "CASH" && (
              <div className="space-y-2">
                <input inputMode="decimal" value={tendered} onChange={(e) => setTendered(e.target.value)}
                  placeholder={t("tendered")} className="vf-input w-full py-2 text-right text-lg font-semibold" />
                <div className="grid grid-cols-4 gap-2">
                  {[Math.ceil(totals.total), 100, 200, 500].filter((v, i, a) => a.indexOf(v) === i).slice(0, 4).map((v) => (
                    <button key={v} onClick={() => setTendered(String(v))} className="vf-btn-secondary py-1.5 text-xs">{v} kr</button>
                  ))}
                </div>
                {tenderedNum > 0 && (
                  <div className="flex justify-between text-sm font-semibold"
                    style={{ color: changeDue >= 0 ? "var(--vf-success)" : "var(--vf-danger)" }}>
                    <span>{changeDue >= 0 ? t("change") : t("insufficient")}</span>
                    <span>{fmt(Math.abs(changeDue))}</span>
                  </div>
                )}
              </div>
            )}

            <button onClick={completeSale} disabled={!canPay || cart.length === 0 || paying}
              className="vf-btn w-full justify-center py-3 text-base disabled:opacity-40">
              {paying ? <Loader2 className="h-5 w-5 animate-spin" /> : `${t("completeSale")} · ${fmt(totals.total)}`}
            </button>
          </div>
        </aside>
      </div>

      {/* ── Scan toast ── */}
      {toast && (
        <div className="pointer-events-none fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full px-4 py-2 text-sm font-semibold text-white shadow-lg"
          style={{ background: toast.kind === "ok" ? "var(--vf-success)" : "var(--vf-danger)" }}>
          {toast.text}
        </div>
      )}

      {/* ── Camera scanner overlay ── */}
      {cameraOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
          <div className="relative w-full max-w-lg rounded-2xl p-4" style={{ background: "var(--vf-bg-surface)" }}>
            <button onClick={() => setCameraOpen(false)} className="absolute right-3 top-3 vf-text-2"><X className="h-5 w-5" /></button>
            <BarcodeScanner
              onResult={(code: string) => { setCameraOpen(false); scan(code); }}
              onClose={() => setCameraOpen(false)}
            />
          </div>
        </div>
      )}

      {/* ── Sale complete overlay ── */}
      {sale && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-sm rounded-2xl border p-8 text-center space-y-4"
            style={{ background: "var(--vf-bg-surface)", borderColor: "var(--vf-border)" }}>
            <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-500" />
            <div>
              <h2 className="text-2xl font-bold vf-text-1">{t("paidTitle")}</h2>
              <p className="mt-1 text-sm vf-text-3">{sale.sale_number}</p>
            </div>
            <p className="text-3xl font-bold vf-text-1">{fmt(parseFloat(sale.total))}</p>
            {sale.change_due && parseFloat(sale.change_due) > 0 && (
              <div className="rounded-lg py-2 text-lg font-semibold"
                style={{ background: "var(--vf-success-bg)", color: "var(--vf-success)" }}>
                {t("changeDue")}: {fmt(parseFloat(sale.change_due))}
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 pt-2">
              <button onClick={() => api.downloadBlob(`/api/pos/sales/${sale.id}/receipt`, `kvitto-${sale.sale_number}.pdf`)}
                className="vf-btn-secondary flex items-center justify-center gap-2 py-2.5">
                <Printer className="h-4 w-4" />{t("receiptPdf")}
              </button>
              <button onClick={newSale} className="vf-btn justify-center py-2.5">{t("newSale")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
