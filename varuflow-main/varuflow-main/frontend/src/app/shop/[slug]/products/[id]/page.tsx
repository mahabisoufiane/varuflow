"use client";

import { CartProvider, useCart } from "@/lib/cart-store";
import { useEffect, useState } from "react";
import Link from "next/link";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Product {
  id: string;
  name: string;
  sku: string;
  description: string | null;
  price: string | null;
  tax_rate: string;
  image_url: string | null;
}

function ProductDetail({ slug, productId }: { slug: string; productId: string }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const { addItem } = useCart();

  useEffect(() => {
    fetch(`${BASE}/api/shop/${slug}/products/${productId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setProduct)
      .catch(() => setError("Product not found"));
  }, [slug, productId]);

  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-gray-500">{error}</p>
    </div>
  );

  if (!product) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="h-8 w-8 rounded-full border-2 border-gray-300 border-t-gray-800 animate-spin" />
    </div>
  );

  const priceExVat = product.price ? parseFloat(product.price) : 0;
  const taxRate = parseFloat(product.tax_rate) || 0.25;
  const priceIncVat = priceExVat * (1 + taxRate);

  const handleAddToCart = async () => {
    setAdding(true);
    try {
      await addItem(product.id, 1);
      setAdded(true);
      setTimeout(() => setAdded(false), 2000);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <Link href={`/shop/${slug}`} className="text-sm text-gray-500 hover:text-gray-800 mb-6 inline-block">
        ← Back to shop
      </Link>
      <div className="grid md:grid-cols-2 gap-8">
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} className="w-full rounded-xl object-cover" />
        ) : (
          <div className="w-full h-64 bg-gray-100 rounded-xl flex items-center justify-center text-gray-400">
            No image
          </div>
        )}
        <div className="flex flex-col gap-4">
          <h1 className="text-2xl font-bold">{product.name}</h1>
          {product.sku && <p className="text-xs text-gray-400">SKU: {product.sku}</p>}
          {product.description && <p className="text-gray-600">{product.description}</p>}
          <div className="mt-2">
            <p className="text-2xl font-semibold">{priceIncVat.toFixed(2)}</p>
            <p className="text-xs text-gray-400">incl. {(taxRate * 100).toFixed(0)}% VAT</p>
          </div>
          <button
            onClick={handleAddToCart}
            disabled={adding || !product.price}
            className="mt-4 px-6 py-3 rounded-lg bg-gray-900 text-white font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {added ? "Added ✓" : adding ? "Adding…" : "Add to Cart"}
          </button>
          <Link
            href={`/shop/${slug}/cart`}
            className="text-center text-sm text-gray-500 hover:text-gray-800"
          >
            View Cart
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ProductPage({ params }: { params: { slug: string; id: string } }) {
  return (
    <CartProvider slug={params.slug}>
      <header className="border-b bg-white px-4 py-4">
        <div className="mx-auto max-w-3xl flex items-center">
          <Link href={`/shop/${params.slug}`} className="font-semibold text-gray-900">
            ← Shop
          </Link>
        </div>
      </header>
      <main>
        <ProductDetail slug={params.slug} productId={params.id} />
      </main>
    </CartProvider>
  );
}
