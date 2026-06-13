"use client";

import { CartProvider } from "@/lib/cart-store";
import { useEffect, useState } from "react";
import Link from "next/link";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Product {
  id: string;
  name: string;
  sku: string;
  price: string | null;
  image_url: string | null;
  slug: string | null;
}

interface Storefront {
  name: string;
  tagline: string | null;
  logo_url: string | null;
  primary_color: string | null;
  currency: string;
}

export default function StorefrontPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [storefront, setStorefront] = useState<Storefront | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${BASE}/api/shop/${slug}`).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
      fetch(`${BASE}/api/shop/${slug}/products?per_page=12`).then((r) => (r.ok ? r.json() : { items: [] })),
    ])
      .then(([sf, prod]) => {
        setStorefront(sf);
        setProducts(prod.items ?? []);
      })
      .catch(() => setError("Shop not found"));
  }, [slug]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">{error}</p>
      </div>
    );
  }

  if (!storefront) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-gray-300 border-t-gray-800 animate-spin" />
      </div>
    );
  }

  const accentColor = storefront.primary_color ?? "#1a2332";

  return (
    <CartProvider slug={slug}>
      <div className="min-h-screen">
        {/* Header */}
        <header className="border-b bg-white shadow-sm">
          <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {storefront.logo_url ? (
                <img src={storefront.logo_url} alt={storefront.name} className="h-8 w-auto" />
              ) : (
                <div className="h-8 w-8 rounded" style={{ backgroundColor: accentColor }} />
              )}
              <span className="font-semibold text-lg">{storefront.name}</span>
            </div>
            <Link
              href={`/shop/${slug}/cart`}
              className="text-sm font-medium px-4 py-2 rounded-lg border hover:bg-gray-50 transition-colors"
            >
              Cart
            </Link>
          </div>
        </header>

        {/* Hero */}
        {storefront.tagline && (
          <div className="py-12 px-4 text-center" style={{ backgroundColor: accentColor }}>
            <p className="text-white text-xl font-light">{storefront.tagline}</p>
          </div>
        )}

        {/* Products */}
        <main className="mx-auto max-w-6xl px-4 py-10">
          <h2 className="text-2xl font-bold mb-6">Products</h2>
          {products.length === 0 ? (
            <p className="text-gray-500">No products available yet.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
              {products.map((p) => (
                <Link
                  key={p.id}
                  href={`/shop/${slug}/products/${p.id}`}
                  className="group border rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow"
                >
                  {p.image_url ? (
                    <img src={p.image_url} alt={p.name} className="w-full h-40 object-cover" />
                  ) : (
                    <div className="w-full h-40 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">
                      No image
                    </div>
                  )}
                  <div className="p-3">
                    <p className="font-medium text-sm truncate">{p.name}</p>
                    {p.price && (
                      <p className="text-sm text-gray-600 mt-1">
                        {storefront.currency} {parseFloat(p.price).toFixed(2)}
                      </p>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="border-t py-6 text-center text-xs text-gray-400">
          Powered by Varuflow
        </footer>
      </div>
    </CartProvider>
  );
}
