"use client";

import { CartProvider, useCart } from "@/lib/cart-store";
import { useState } from "react";
import Link from "next/link";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function CartPageInner({ slug }: { slug: string }) {
  const { guestToken, items, loading, subtotal, updateQty, removeItem, setEmail, customerEmail } = useCart();

  const [name, setName] = useState("");
  const [email, setEmailLocal] = useState("");
  const [address, setAddress] = useState({ line1: "", city: "", postal_code: "", country: "SE" });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleCheckout = async () => {
    if (!name || !email || !address.line1 || !address.city || !address.postal_code) {
      setFormError("Please fill in all required fields.");
      return;
    }
    if (!guestToken) {
      setFormError("Cart session missing. Please add items first.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      setEmail(email);
      const res = await fetch(`${BASE}/api/shop/${slug}/cart/${guestToken}/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: name,
          customer_email: email,
          shipping_address: address,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "Checkout failed");
      }
      const { checkout_url } = await res.json();
      window.location.href = checkout_url;
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 rounded-full border-2 border-gray-300 border-t-gray-800 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-6">Your Cart</h1>

      {items.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500 mb-4">Your cart is empty.</p>
          <Link href={`/shop/${slug}`} className="text-sm font-medium underline">
            Continue shopping
          </Link>
        </div>
      ) : (
        <>
          {/* Cart items */}
          <div className="divide-y border rounded-xl overflow-hidden mb-6">
            {items.map((item) => (
              <div key={item.product_id} className="flex items-center gap-4 px-4 py-3 bg-white">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{item.description}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {parseFloat(item.unit_price).toFixed(2)} each
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => updateQty(item.product_id, Math.max(1, item.qty - 1))}
                    className="w-6 h-6 rounded border text-sm flex items-center justify-center hover:bg-gray-50"
                  >
                    −
                  </button>
                  <span className="w-6 text-center text-sm">{item.qty}</span>
                  <button
                    onClick={() => updateQty(item.product_id, item.qty + 1)}
                    className="w-6 h-6 rounded border text-sm flex items-center justify-center hover:bg-gray-50"
                  >
                    +
                  </button>
                </div>
                <p className="text-sm font-medium w-16 text-right">
                  {(parseFloat(item.unit_price) * item.qty).toFixed(2)}
                </p>
                <button
                  onClick={() => removeItem(item.product_id)}
                  className="text-gray-400 hover:text-red-500 text-xs"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <div className="text-right text-sm text-gray-500 mb-2">
            Subtotal (excl. VAT): <strong>{subtotal}</strong>
          </div>

          {/* Customer info form */}
          <div className="border rounded-xl bg-white p-6 space-y-4 mt-6">
            <h2 className="font-semibold">Delivery details</h2>
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-600">Full name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                  placeholder="Erik Lindqvist"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Email *</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmailLocal(e.target.value)}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                  placeholder="erik@example.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Address *</label>
                <input
                  type="text"
                  value={address.line1}
                  onChange={(e) => setAddress((a) => ({ ...a, line1: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                  placeholder="Storgatan 1"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">Postal code *</label>
                  <input
                    type="text"
                    value={address.postal_code}
                    onChange={(e) => setAddress((a) => ({ ...a, postal_code: e.target.value }))}
                    className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                    placeholder="12345"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">City *</label>
                  <input
                    type="text"
                    value={address.city}
                    onChange={(e) => setAddress((a) => ({ ...a, city: e.target.value }))}
                    className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                    placeholder="Stockholm"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Country</label>
                <select
                  value={address.country}
                  onChange={(e) => setAddress((a) => ({ ...a, country: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                >
                  <option value="SE">Sweden</option>
                  <option value="NO">Norway</option>
                  <option value="DK">Denmark</option>
                  <option value="FI">Finland</option>
                  <option value="DE">Germany</option>
                </select>
              </div>
            </div>
          </div>

          {formError && (
            <p className="mt-3 text-sm text-red-600">{formError}</p>
          )}

          <button
            onClick={handleCheckout}
            disabled={submitting || items.length === 0}
            className="mt-6 w-full py-3 rounded-xl bg-gray-900 text-white font-semibold text-sm hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {submitting ? "Redirecting to payment…" : "Pay Now →"}
          </button>

          <p className="mt-3 text-xs text-center text-gray-400">
            Secure payment via Stripe. Card, Klarna, Swish accepted.
          </p>
        </>
      )}
    </div>
  );
}

export default function CartPage({ params }: { params: { slug: string } }) {
  return (
    <CartProvider slug={params.slug}>
      <header className="border-b bg-white px-4 py-4 mb-2">
        <div className="mx-auto max-w-2xl flex items-center justify-between">
          <Link href={`/shop/${params.slug}`} className="font-semibold text-gray-900">
            ← Continue shopping
          </Link>
        </div>
      </header>
      <main>
        <CartPageInner slug={params.slug} />
      </main>
    </CartProvider>
  );
}
