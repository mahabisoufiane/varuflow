import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Search, ScanLine } from "lucide-react";
import { usePosT } from "../lib/i18n";
import { api } from "../lib/api";
import { usePos, type PosProduct } from "../lib/pos-store";
import BarcodeScanner from "./BarcodeScanner";
import { toast } from "sonner";

interface Props {
  searchRef: React.RefObject<HTMLInputElement | null>;
}

const PLACEHOLDER_COLORS = [
  "bg-violet-100 text-violet-500",
  "bg-blue-100 text-blue-500",
  "bg-rose-100 text-rose-500",
  "bg-amber-100 text-amber-500",
  "bg-teal-100 text-teal-500",
  "bg-pink-100 text-pink-500",
];

function colorFor(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff;
  return PLACEHOLDER_COLORS[h % PLACEHOLDER_COLORS.length];
}

export default function PosProductGrid({ searchRef }: Props) {
  const t = usePosT();
  const { addToCart } = usePos();

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [products, setProducts] = useState<PosProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const [pulsingId, setPulsingId] = useState<string | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const p of products) if (p.category) set.add(p.category);
    return ["all", ...Array.from(set).sort()];
  }, [products]);

  const visible = useMemo(
    () => category === "all" ? products : products.filter((p) => (p.category ?? "") === category),
    [products, category],
  );

  const handleBarcode = useCallback(async (raw: string) => {
    const barcode = raw.trim();
    if (!barcode) return;
    try {
      const product = await api.get<PosProduct>(`/api/pos/lookup?barcode=${encodeURIComponent(barcode)}`);
      addToCart(product, 1);
      setPulsingId(product.id);
      setTimeout(() => setPulsingId(null), 300);
      setQuery("");
    } catch {
      toast.error(`No product for "${barcode}"`);
    }
  }, [addToCart]);

  function stockBadge(p: PosProduct) {
    if (p.stock <= 0) return "bg-red-100 text-red-600 border border-red-200";
    if (p.stock < 5)  return "bg-amber-100 text-amber-700 border border-amber-200";
    return "bg-emerald-100 text-emerald-700 border border-emerald-200";
  }

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Search row */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            ref={searchRef}
            type="search"
            autoFocus
            inputMode="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); handleBarcode(query); }
              else if (e.key === "Escape") setQuery("");
            }}
            placeholder={t("search_placeholder")}
            className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-100"
            data-testid="pos-search"
          />
        </div>
        <button
          type="button"
          onClick={() => setScannerOpen(true)}
          title="Scan barcode"
          className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white shadow-sm text-slate-500 hover:border-emerald-400 hover:text-emerald-600 transition"
        >
          <ScanLine className="h-5 w-5" />
        </button>
      </div>

      {/* Category pills */}
      {categories.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
          {categories.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              className={`whitespace-nowrap rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                category === c
                  ? "bg-slate-900 text-white shadow-sm"
                  : "bg-white text-slate-600 border border-slate-200 hover:border-slate-400"
              }`}
            >
              {c === "all" ? t("category_all") : c}
            </button>
          ))}
        </div>
      )}

      {/* Product grid */}
      <div
        className="grid flex-1 auto-rows-max grid-cols-2 gap-3 overflow-y-auto pb-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
        data-testid="pos-product-grid"
      >
        {loading && Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="animate-pulse rounded-2xl bg-slate-200 h-40" />
        ))}

        {!loading && visible.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              addToCart(p, 1);
              setPulsingId(p.id);
              setTimeout(() => setPulsingId(null), 250);
            }}
            className={`group flex flex-col overflow-hidden rounded-2xl bg-white shadow-sm border transition active:scale-[0.96] text-left ${
              pulsingId === p.id
                ? "border-emerald-400 ring-2 ring-emerald-200 shadow-emerald-100"
                : "border-transparent hover:border-slate-200 hover:shadow-md"
            }`}
          >
            {/* Image / placeholder */}
            {p.image_url ? (
              <img
                src={p.image_url}
                alt={p.name}
                className="h-28 w-full object-cover"
                loading="lazy"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
              />
            ) : (
              <div className={`flex h-28 w-full items-center justify-center text-3xl font-black select-none ${colorFor(p.name)}`}>
                {p.name.charAt(0).toUpperCase()}
              </div>
            )}

            {/* Details */}
            <div className="flex flex-col gap-1 p-3">
              <p className="line-clamp-2 text-xs font-semibold leading-tight text-slate-800">{p.name}</p>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-sm font-bold text-emerald-600">
                  {Number(p.sell_price).toFixed(2)}
                  <span className="ml-0.5 text-[10px] font-normal text-slate-400">SEK</span>
                </span>
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${stockBadge(p)}`}>
                  {p.stock}
                </span>
              </div>
            </div>
          </button>
        ))}

        {!loading && visible.length === 0 && (
          <div className="col-span-full flex flex-col items-center justify-center py-16 text-slate-400">
            <Search className="mb-2 h-8 w-8 opacity-30" />
            <p className="text-sm">No products found</p>
          </div>
        )}
      </div>

      {scannerOpen && (
        <BarcodeScanner
          onDetected={(barcode) => { setScannerOpen(false); handleBarcode(barcode); }}
          onClose={() => setScannerOpen(false)}
        />
      )}
    </div>
  );
}
