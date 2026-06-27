/**
 * File: src/lib/pos-store.tsx
 * Purpose: Single-source-of-truth state for the tablet-optimized POS.
 *
 * Implemented as a React Context so we don't pull Zustand in for one
 * page (same reason the frontend has no Redux / no Jotai). Every write
 * action on the cart, payment method, discount and session lives here
 * — individual components never own their own useState for those
 * fields. This matches the rule in the Item 10 spec: *"pos-store.ts
 * must be the single source of truth — no local useState for cart"*.
 *
 * All server mutations go through `api` from `./api`, which
 * means they inherit the offline queue. A POS sale rung up
 * while the tablet is offline is persisted to IndexedDB and replayed
 * when the Wi-Fi comes back.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { openDB } from "idb";
import { api } from "./api";

export interface PosProduct {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  sell_price: string;
  tax_rate: string;
  unit: string;
  stock: number;
  category?: string | null;
  image_url?: string | null;
}

export interface CartItem {
  product: PosProduct;
  qty: number;
  unit_price: number; // SEK, already excl. VAT
  discount_pct: number; // 0–100, per-line
}

export interface PosSession {
  id: string;
  status: "OPEN" | "CLOSED";
  opened_at: string;
  closed_at: string | null;
  opening_float?: string | null;
}

export interface PosSale {
  id: string;
  sale_number: string;
  total: string;
  subtotal: string;
  vat_amount: string;
  change_due: string | null;
  account_invoice_id: string | null;
  account_invoice_number: string | null;
}

/** Minimal customer info shown on the POS cart for B2B traceability. */
export interface PosCustomer {
  id: string;
  company_name: string;
  email: string | null;
  org_number: string | null;
}

export type PaymentMethod = "cash" | "card" | "swish" | "account";
export type DiscountType = "flat" | "pct";

interface PosState {
  session: PosSession | null;
  cart: CartItem[];
  paymentMethod: PaymentMethod;
  cashTendered: number;
  discountType: DiscountType;
  discountValue: number;
  lastSale: PosSale | null;
  submitting: boolean;
  selectedCustomer: PosCustomer | null;

  addToCart: (product: PosProduct, qty?: number) => void;
  removeFromCart: (productId: string) => void;
  updateQty: (productId: string, qty: number) => void;
  updateLineDiscount: (productId: string, discountPct: number) => void;
  clearCart: () => void;
  setPaymentMethod: (m: PaymentMethod) => void;
  setCashTendered: (amount: number) => void;
  setDiscount: (type: DiscountType, value: number) => void;
  setSelectedCustomer: (customer: PosCustomer | null) => void;
  submitSale: () => Promise<PosSale | null>;
  openSession: (openingFloat: number) => Promise<void>;
  closeSession: (countedCash: number) => Promise<void>;
  loadOpenSession: () => Promise<void>;
  dismissLastSale: () => void;
}

const PosContext = createContext<PosState | null>(null);

/** Swedish standard VAT rate — surfaced as a constant so the cart total
 *  and the i18n copy stay in lock-step. */
export const VAT_RATE = 0.25;

/** Compute totals for a cart snapshot. Pure function — tested in
 *  `scripts/test_pos_tablet.mjs` via structural assertion. */
export function computeTotals(
  cart: CartItem[],
  discountType: DiscountType,
  discountValue: number,
) {
  const subtotal = cart.reduce((acc, it) => {
    const linePre = it.unit_price * it.qty;
    const lineAfterLineDiscount = linePre * (1 - it.discount_pct / 100);
    return acc + lineAfterLineDiscount;
  }, 0);

  const discount =
    discountType === "pct"
      ? subtotal * (Math.max(0, Math.min(100, discountValue)) / 100)
      : Math.min(subtotal, Math.max(0, discountValue));

  const netSubtotal = Math.max(0, subtotal - discount);
  const vat = netSubtotal * VAT_RATE;
  const total = netSubtotal + vat;
  return { subtotal, discount, netSubtotal, vat, total };
}

export function PosProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<PosSession | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [paymentMethod, setPaymentMethodState] = useState<PaymentMethod>("cash");
  const [cashTendered, setCashTenderedState] = useState(0);
  const [discountType, setDiscountType] = useState<DiscountType>("flat");
  const [discountValue, setDiscountValue] = useState(0);
  const [lastSale, setLastSale] = useState<PosSale | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedCustomer, setSelectedCustomerState] = useState<PosCustomer | null>(null);

  // ── Cart persistence to IndexedDB ──────────────────────────────────────
  const CART_DB = "vf-pos-cart";
  const CART_STORE = "current";
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Restore persisted cart on mount
  useEffect(() => {
    (async () => {
      try {
        const db = await openDB(CART_DB, 1, {
          upgrade(d) { if (!d.objectStoreNames.contains(CART_STORE)) d.createObjectStore(CART_STORE); },
        });
        const saved = await db.get(CART_STORE, "active") as {
          cart: CartItem[];
          paymentMethod: PaymentMethod;
          discountType: DiscountType;
          discountValue: number;
          customerId: string | null;
          customerData: PosCustomer | null;
        } | undefined;
        if (saved && saved.cart.length > 0) {
          setCart(saved.cart);
          setPaymentMethodState(saved.paymentMethod);
          setDiscountType(saved.discountType);
          setDiscountValue(saved.discountValue);
          if (saved.customerData) setSelectedCustomerState(saved.customerData);
        }
      } catch { /* IDB unavailable — continue with empty cart */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist cart to IndexedDB on every change (debounced 300ms)
  useEffect(() => {
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      (async () => {
        try {
          const db = await openDB(CART_DB, 1, {
            upgrade(d) { if (!d.objectStoreNames.contains(CART_STORE)) d.createObjectStore(CART_STORE); },
          });
          if (cart.length === 0) {
            await db.delete(CART_STORE, "active");
          } else {
            await db.put(CART_STORE, {
              cart,
              paymentMethod,
              discountType,
              discountValue,
              customerId: selectedCustomer?.id ?? null,
              customerData: selectedCustomer,
            }, "active");
          }
        } catch { /* non-fatal */ }
      })();
    }, 300);
    return () => { if (persistTimer.current) clearTimeout(persistTimer.current); };
  }, [cart, paymentMethod, discountType, discountValue, selectedCustomer]);

  const addToCart = useCallback((product: PosProduct, qty = 1) => {
    setCart((prev) => {
      const existing = prev.find((it) => it.product.id === product.id);
      if (existing) {
        return prev.map((it) =>
          it.product.id === product.id ? { ...it, qty: it.qty + qty } : it,
        );
      }
      return [
        ...prev,
        {
          product,
          qty,
          unit_price: Number(product.sell_price),
          discount_pct: 0,
        },
      ];
    });
  }, []);

  const removeFromCart = useCallback((productId: string) => {
    setCart((prev) => prev.filter((it) => it.product.id !== productId));
  }, []);

  const updateQty = useCallback(
    (productId: string, qty: number) => {
      if (qty <= 0) {
        removeFromCart(productId);
        return;
      }
      setCart((prev) =>
        prev.map((it) =>
          it.product.id === productId ? { ...it, qty } : it,
        ),
      );
    },
    [removeFromCart],
  );

  const updateLineDiscount = useCallback((productId: string, discountPct: number) => {
    setCart((prev) =>
      prev.map((it) =>
        it.product.id === productId
          ? { ...it, discount_pct: Math.max(0, Math.min(100, discountPct)) }
          : it,
      ),
    );
  }, []);

  const clearCart = useCallback(() => {
    setCart([]);
    setCashTenderedState(0);
    setDiscountValue(0);
    setSelectedCustomerState(null);
    // Eagerly clear persisted cart
    openDB(CART_DB, 1, {
      upgrade(d) { if (!d.objectStoreNames.contains(CART_STORE)) d.createObjectStore(CART_STORE); },
    }).then((db) => db.delete(CART_STORE, "active")).catch(() => {});
  }, []);

  const setPaymentMethod = useCallback((m: PaymentMethod) => {
    setPaymentMethodState(m);
    // Reset tendered cash when switching away from cash so "change due"
    // doesn't linger on a card / swish sale.
    if (m !== "cash") setCashTenderedState(0);
  }, []);

  const setCashTendered = useCallback((v: number) => setCashTenderedState(v), []);
  const setDiscount = useCallback((t: DiscountType, v: number) => {
    setDiscountType(t);
    setDiscountValue(v);
  }, []);

  const setSelectedCustomer = useCallback((c: PosCustomer | null) => {
    setSelectedCustomerState(c);
  }, []);

  const loadOpenSession = useCallback(async () => {
    try {
      // Backend /api/pos/sessions returns the 50 most recent regardless
      // of status — filter client-side for the one still OPEN. If none,
      // UI falls back to the "Öppna session" CTA.
      const sessions = await api.get<PosSession[]>("/api/pos/sessions");
      const open = sessions.find((s) => s.status === "OPEN") ?? null;
      setSession(open);
    } catch {
      // List endpoint errors are silently swallowed — the UI falls back
      // to the "Öppna session" CTA which forces the cashier to resolve.
    }
  }, []);

  const openSession = useCallback(async (openingFloat: number) => {
    const s = await api.post<PosSession>("/api/pos/sessions", {
      opening_float: openingFloat,
    });
    setSession(s);
  }, []);

  const closeSession = useCallback(
    async (countedCash: number) => {
      if (!session) return;
      const s = await api.patch<PosSession>(
        `/api/pos/sessions/${session.id}/close`,
        { counted_cash: countedCash },
      );
      setSession(s);
    },
    [session],
  );

  const submitSale = useCallback(async () => {
    if (!session || cart.length === 0) return null;
    setSubmitting(true);
    try {
      const totals = computeTotals(cart, discountType, discountValue);
      const payload = {
        session_id: session.id,
        payment_method: paymentMethod.toUpperCase(),
        amount_tendered: paymentMethod === "cash" ? cashTendered : null,
        customer_id: selectedCustomer?.id ?? null,
        items: cart.map((it) => ({
          product_id: it.product.id,
          description: it.product.name,
          quantity: it.qty,
          unit_price: it.unit_price,
          tax_rate: VAT_RATE * 100,
          discount_pct: it.discount_pct,
        })),
        discount_total:
          discountType === "flat"
            ? discountValue
            : totals.subtotal * (discountValue / 100),
      };
      const sale = await api.post<PosSale>("/api/pos/sales", payload);
      setLastSale(sale);
      clearCart();
      return sale;
    } finally {
      setSubmitting(false);
    }
  }, [session, cart, paymentMethod, cashTendered, discountType, discountValue, selectedCustomer, clearCart]);

  const dismissLastSale = useCallback(() => setLastSale(null), []);

  const value = useMemo<PosState>(
    () => ({
      session,
      cart,
      paymentMethod,
      cashTendered,
      discountType,
      discountValue,
      lastSale,
      submitting,
      selectedCustomer,
      addToCart,
      removeFromCart,
      updateQty,
      updateLineDiscount,
      clearCart,
      setPaymentMethod,
      setCashTendered,
      setDiscount,
      setSelectedCustomer,
      submitSale,
      openSession,
      closeSession,
      loadOpenSession,
      dismissLastSale,
    }),
    [
      session, cart, paymentMethod, cashTendered, discountType, discountValue,
      lastSale, submitting, selectedCustomer,
      addToCart, removeFromCart, updateQty, updateLineDiscount, clearCart,
      setPaymentMethod, setCashTendered, setDiscount, setSelectedCustomer,
      submitSale, openSession, closeSession, loadOpenSession, dismissLastSale,
    ],
  );

  return <PosContext.Provider value={value}>{children}</PosContext.Provider>;
}

export function usePos(): PosState {
  const ctx = useContext(PosContext);
  if (!ctx) throw new Error("usePos must be called inside <PosProvider>");
  return ctx;
}
