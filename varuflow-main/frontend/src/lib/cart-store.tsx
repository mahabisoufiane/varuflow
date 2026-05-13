"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface CartItem {
  product_id: string;
  description: string;
  qty: number;
  unit_price: string;
  tax_rate: string;
}

interface CartState {
  cartId: string | null;
  guestToken: string | null;
  items: CartItem[];
  loading: boolean;
  subtotal: string;
}

interface CartActions {
  addItem: (productId: string, qty?: number) => Promise<void>;
  updateQty: (productId: string, qty: number) => Promise<void>;
  removeItem: (productId: string) => Promise<void>;
  setEmail: (email: string) => void;
  customerEmail: string;
  clear: () => void;
}

const CartContext = createContext<CartState & CartActions>({
  cartId: null,
  guestToken: null,
  items: [],
  loading: false,
  subtotal: "0",
  customerEmail: "",
  addItem: async () => {},
  updateQty: async () => {},
  removeItem: async () => {},
  setEmail: () => {},
  clear: () => {},
});

function computeSubtotal(items: CartItem[]): string {
  let total = 0;
  for (const it of items) {
    total += parseFloat(it.unit_price) * it.qty;
  }
  return total.toFixed(2);
}

export function CartProvider({ slug, children }: { slug: string; children: React.ReactNode }) {
  const storageKey = `vf_cart_${slug}`;
  const [guestToken, setGuestToken] = useState<string | null>(null);
  const [cartId, setCartId] = useState<string | null>(null);
  const [items, setItems] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [customerEmail, setCustomerEmailState] = useState("");

  const ensureCart = useCallback(async (): Promise<string> => {
    if (guestToken) return guestToken;
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed.guestToken) {
          setGuestToken(parsed.guestToken);
          setCartId(parsed.cartId ?? null);
          return parsed.guestToken;
        }
      } catch {
        // ignore
      }
    }
    const res = await fetch(`${BASE}/api/shop/${slug}/cart`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to create cart");
    const data = await res.json();
    setGuestToken(data.guest_token);
    setCartId(data.cart_id);
    localStorage.setItem(storageKey, JSON.stringify({ guestToken: data.guest_token, cartId: data.cart_id }));
    return data.guest_token;
  }, [guestToken, slug, storageKey]);

  // Load cart on mount
  useEffect(() => {
    const stored = localStorage.getItem(storageKey);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored);
      if (!parsed.guestToken) return;
      setGuestToken(parsed.guestToken);
      setCartId(parsed.cartId ?? null);
      setLoading(true);
      fetch(`${BASE}/api/shop/${slug}/cart/${parsed.guestToken}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data) {
            setItems(data.items ?? []);
            setCustomerEmailState(data.customer_email ?? "");
          }
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    } catch {
      // ignore
    }
  }, [slug, storageKey]);

  const addItem = useCallback(
    async (productId: string, qty = 1) => {
      setLoading(true);
      try {
        const token = await ensureCart();
        const res = await fetch(`${BASE}/api/shop/${slug}/cart/${token}/items`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: productId, qty }),
        });
        if (res.ok) {
          const data = await res.json();
          setItems(data.items ?? []);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    },
    [ensureCart, slug]
  );

  const updateQty = useCallback(
    async (productId: string, qty: number) => {
      if (!guestToken) return;
      setLoading(true);
      try {
        const res = await fetch(`${BASE}/api/shop/${slug}/cart/${guestToken}/items/${productId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ qty }),
        });
        if (res.ok) {
          const data = await res.json();
          setItems(data.items ?? []);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    },
    [guestToken, slug]
  );

  const removeItem = useCallback(
    async (productId: string) => {
      if (!guestToken) return;
      setLoading(true);
      try {
        await fetch(`${BASE}/api/shop/${slug}/cart/${guestToken}/items/${productId}`, {
          method: "DELETE",
        });
        setItems((prev) => prev.filter((it) => it.product_id !== productId));
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    },
    [guestToken, slug]
  );

  const setEmail = useCallback((email: string) => {
    setCustomerEmailState(email);
  }, []);

  const clear = useCallback(() => {
    localStorage.removeItem(storageKey);
    setGuestToken(null);
    setCartId(null);
    setItems([]);
  }, [storageKey]);

  return (
    <CartContext.Provider
      value={{
        cartId,
        guestToken,
        items,
        loading,
        subtotal: computeSubtotal(items),
        customerEmail,
        addItem,
        updateQty,
        removeItem,
        setEmail,
        clear,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}
