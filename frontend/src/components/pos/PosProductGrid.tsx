"use client";

/** Left column: debounced product search + category tabs + grid.
 *  Barcode scanners emit characters + Enter, which the onKeyDown below
 *  treats as an instant lookup rather than a full text search. */

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { usePos, type PosProduct } from "@/lib/pos-store";
import { toast } from "sonner";

interface Props {
  searchRef: React.RefObject<HTMLInputElement | null>;
}

export default function PosProductGrid({ searchRef }: Props) {
  const t = useTranslations("pos");
  const { addToCart } = usePos();

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [products, setProducts] = useState<PosProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const [pulsingId, setPulsingId] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced text search. Barcode path bypasses this via onKeyDown.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        setLoading(true);
        const qs = new URLSearchParams();
        if (query.trim()) qs.set("q", query.trim());
        const list = await api.get<PosProduct[]>(`/api/pos/products?${qs.toString()}`);
        setProducts(list);
      } catch {
        setProducts([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const p of products) if (p.category) set.add(p.category);
    return ["all", ...Array.from(set).sort()];
  }, [products]);

  const visible = useMemo(
    () =>
      category === "all"
        ? products
        : products.filter((p) => (p.category ?? "") === category),
    [products, category],
  );

  async function handleBarcode(raw: string) {
    const barcode = raw.trim();
    if (!barcode) return;
    try {
      const product = await api.get<PosProduct>(
        `/api/pos/lookup?barcode=${encodeURIComponent(barcode)}`,
      );
      addToCart(product, 1);
      setPulsingId(product.id);
      setTimeout(() => setPulsingId(null), 300);
      setQuery("");
    } catch {
      toast.error(`No product for "${barcode}"`);
    }
  }

  function stockTone(p: PosProduct): string {
    if (p.stock <= 0) return "bg-red-100 text-red-700";
    if (p.stock < 5) return "bg-amber-100 text-amber-800";
    return "bg-emerald-100 text-emerald-700";
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <input
        ref={searchRef}
        type="search"
        autoFocus
        inputMode="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            handleBarcode(query);
          } else if (e.key === "Escape") {
            setQuery("");
          }
        }}
        placeholder={t("search_placeholder")}
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:focus:border-emerald-400"
        data-testid="pos-search"
      />

      <div className="flex gap-2 overflow-x-auto pb-1">
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setCategory(c)}
            className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition ${
              category === c
                ? "bg-emerald-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            }`}
          >
            {c === "all" ? t("category_all") : c}
          </button>
        ))}
      </div>

      <div
        className="grid grid-cols-2 gap-3 overflow-y-auto md:grid-cols-3 lg:grid-cols-4"
        data-testid="pos-product-grid"
      >
        {visible.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              addToCart(p, 1);
              setPulsingId(p.id);
              setTimeout(() => setPulsingId(null), 300);
            }}
            className={`flex min-h-[80px] flex-col items-start justify-between rounded-xl border border-gray-200 bg-white p-3 text-left shadow-sm transition active:scale-[0.97] dark:border-gray-700 dark:bg-gray-800 ${
              pulsingId === p.id ? "ring-2 ring-emerald-400" : ""
            }`}
          >
            <div className="flex w-full items-start justify-between gap-2">
              <span className="line-clamp-2 text-sm font-semibold">{p.name}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${stockTone(p)}`}>
                {p.stock}
              </span>
            </div>
            <span className="mt-2 text-base font-bold text-emerald-700">
              {Number(p.sell_price).toFixed(2)} SEK
            </span>
          </button>
        ))}
        {!loading && visible.length === 0 && (
          <p className="col-span-full py-10 text-center text-sm text-gray-400 dark:text-gray-500">
            —
          </p>
        )}
      </div>
    </div>
  );
}
