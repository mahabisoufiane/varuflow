"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  portalApi,
  PORTAL_TOKEN_KEY,
  PORTAL_CUSTOMER_KEY,
} from "@/lib/portal-client";

const PORTAL_REORDER_KEY = "portal_reorder";

interface CatalogueItem {
  product_id: string;
  name: string;
  sku: string;
  unit: string;
  price: string;
  price_is_override: boolean;
  stock_available: number;
  image_url: string | null;
  description: string | null;
}

interface CatalogueResponse {
  org_name: string;
  ordering_enabled: boolean;
  items: CatalogueItem[];
}

interface CartLine {
  product_id: string;
  name: string;
  unit: string;
  price: number;
  quantity: number;
}

interface PlacedOrder {
  order_number: string;
  total_sek: string;
}

const formatSek = (value: number | string) =>
  Number(value).toLocaleString("sv-SE", { minimumFractionDigits: 2 });

export default function PortalCataloguePage() {
  const router = useRouter();
  const [catalogue, setCatalogue] = useState<CatalogueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [placed, setPlaced] = useState<PlacedOrder | null>(null);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem(PORTAL_TOKEN_KEY) : null;
    if (!token) {
      router.replace("/portal/login");
      return;
    }
    portalApi
      .get<CatalogueResponse>("/api/portal/catalogue")
      .then((data) => {
        setCatalogue(data);
        // Pre-fill cart from reorder (set by orders page)
        const reorderRaw = localStorage.getItem(PORTAL_REORDER_KEY);
        if (reorderRaw) {
          try {
            const lines: { product_id: string; quantity: number }[] = JSON.parse(reorderRaw);
            const preCart: Record<string, number> = {};
            for (const l of lines) preCart[l.product_id] = l.quantity;
            setCart(preCart);
          } catch { /* ignore malformed */ }
          localStorage.removeItem(PORTAL_REORDER_KEY);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [router]);

  const cartLines: CartLine[] = useMemo(() => {
    if (!catalogue) return [];
    return Object.entries(cart)
      .filter(([, qty]) => qty > 0)
      .map(([pid, qty]) => {
        const item = catalogue.items.find((i) => i.product_id === pid);
        if (!item) return null;
        return {
          product_id: pid,
          name: item.name,
          unit: item.unit,
          price: Number(item.price),
          quantity: qty,
        };
      })
      .filter((v): v is CartLine => v !== null);
  }, [cart, catalogue]);

  const cartTotal = useMemo(
    () => cartLines.reduce((s, l) => s + l.price * l.quantity, 0),
    [cartLines],
  );

  function setQty(productId: string, qty: number) {
    setCart((c) => {
      const next = { ...c };
      if (qty <= 0) {
        delete next[productId];
      } else {
        next[productId] = qty;
      }
      return next;
    });
  }

  async function submitOrder() {
    if (cartLines.length === 0 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await portalApi.post<PlacedOrder>("/api/portal/orders", {
        lines: cartLines.map((l) => ({
          product_id: l.product_id,
          quantity: l.quantity,
        })),
        notes: notes.trim() || null,
      });
      setPlaced(res);
      setCart({});
      setNotes("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  }

  function handleSignOut() {
    localStorage.removeItem(PORTAL_TOKEN_KEY);
    localStorage.removeItem(PORTAL_CUSTOMER_KEY);
    router.push("/portal/login");
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-gray-100 animate-pulse" />
        ))}
      </div>
    );
  }

  if (!catalogue) {
    return (
      <div className="rounded-xl border bg-white p-8 text-center text-sm text-red-600">
        {error ?? "Failed to load catalogue."}
      </div>
    );
  }

  if (placed) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border bg-white p-8 text-center">
          <h1 className="text-xl font-bold text-[#1a2332]">Tack för din beställning</h1>
          <p className="mt-2 text-sm text-gray-600">
            Ordernummer <span className="font-mono font-semibold">{placed.order_number}</span> har
            skickats till {catalogue.org_name}. Totalt{" "}
            <span className="font-semibold">{formatSek(placed.total_sek)} SEK</span>.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              onClick={() => setPlaced(null)}
              className="rounded-md bg-[#1a2332] px-4 py-2 text-sm font-medium text-white"
            >
              Fortsätt handla
            </button>
            <Link
              href="/portal/orders"
              className="rounded-md border px-4 py-2 text-sm font-medium text-gray-700"
            >
              Se orderhistorik
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1a2332]">Katalog</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">{catalogue.org_name}</p>
        </div>
        <div className="flex gap-3 text-xs">
          <Link href="/portal/invoices" className="underline text-muted-foreground">
            Fakturor
          </Link>
          <Link href="/portal/orders" className="underline text-muted-foreground">
            Ordrar
          </Link>
          <button
            onClick={handleSignOut}
            className="underline text-muted-foreground hover:text-gray-900"
          >
            Logga ut
          </button>
        </div>
      </div>

      {!catalogue.ordering_enabled && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          Självbetjäningsorder är inte aktiverad för ditt konto. Kontakta{" "}
          {catalogue.org_name} för att aktivera.
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {catalogue.items.map((item) => {
          const qty = cart[item.product_id] ?? 0;
          const disabled = !catalogue.ordering_enabled || item.stock_available <= 0;
          return (
            <div
              key={item.product_id}
              className="rounded-xl border bg-white p-4 flex flex-col gap-2"
            >
              <div>
                <p className="font-semibold text-gray-900">{item.name}</p>
                <p className="text-xs text-muted-foreground">
                  {item.sku} · Lager: {item.stock_available} {item.unit}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-mono font-semibold text-gray-900">
                    {formatSek(item.price)} SEK
                  </span>
                  {item.price_is_override && (
                    <span className="ml-2 rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                      Ditt pris
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={0}
                    max={item.stock_available}
                    value={qty}
                    onChange={(e) =>
                      setQty(item.product_id, Math.max(0, Number(e.target.value) || 0))
                    }
                    disabled={disabled}
                    className="w-16 rounded-md border px-2 py-1 text-sm"
                  />
                  <button
                    onClick={() => setQty(item.product_id, Math.max(1, qty || 1))}
                    disabled={disabled}
                    className="rounded-md bg-[#1a2332] px-3 py-1.5 text-xs font-medium text-white disabled:bg-gray-300"
                  >
                    Lägg i varukorg
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {cartLines.length > 0 && (
        <div className="sticky bottom-4 mt-8 rounded-xl border bg-white p-5 shadow-lg">
          <h2 className="font-semibold text-[#1a2332]">Varukorg</h2>
          <ul className="mt-2 divide-y text-sm">
            {cartLines.map((line) => (
              <li
                key={line.product_id}
                className="flex items-center justify-between py-2"
              >
                <span>
                  {line.name} × {line.quantity} {line.unit}
                </span>
                <span className="font-mono">
                  {formatSek(line.price * line.quantity)} SEK
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center justify-between text-sm font-semibold">
            <span>Total (ex. moms)</span>
            <span className="font-mono">{formatSek(cartTotal)} SEK</span>
          </div>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Meddelande till säljaren (valfritt)"
            maxLength={500}
            className="mt-3 w-full rounded-md border px-3 py-2 text-sm"
            rows={2}
          />
          <button
            onClick={submitOrder}
            disabled={submitting || !catalogue.ordering_enabled}
            className="mt-3 w-full rounded-md bg-[#1a2332] py-2.5 text-sm font-semibold text-white disabled:bg-gray-300"
          >
            {submitting ? "Skickar order…" : "Bekräfta order"}
          </button>
        </div>
      )}
    </div>
  );
}
