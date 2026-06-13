"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CartProvider, useCart } from "@/lib/cart-store";

function SuccessInner({ slug }: { slug: string }) {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const { clear } = useCart();

  useEffect(() => {
    // Clear the cart once the order is confirmed
    clear();
  }, [clear]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="mx-auto h-16 w-16 rounded-full bg-green-100 flex items-center justify-center text-3xl">
          ✓
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Order Confirmed!</h1>
        <p className="text-gray-500">
          Thank you for your purchase. A confirmation email has been sent to you.
        </p>
        {sessionId && (
          <p className="text-xs text-gray-400 font-mono break-all">
            Ref: {sessionId.slice(0, 20)}…
          </p>
        )}
        <Link
          href={`/shop/${slug}`}
          className="inline-block mt-4 px-6 py-3 rounded-xl bg-gray-900 text-white font-medium text-sm hover:bg-gray-700 transition-colors"
        >
          Back to Shop
        </Link>
      </div>
    </div>
  );
}

export default function SuccessPage({ params }: { params: { slug: string } }) {
  return (
    <CartProvider slug={params.slug}>
      <SuccessInner slug={params.slug} />
    </CartProvider>
  );
}
