"use client";

// Labels printer client component (Item 36).
//
// Lets the operator select a subset of products from the catalogue
// and print thermal/sheet barcode labels. Delegates to
// ``/api/labels/print`` which streams a PDF; the browser opens or
// saves it via :func:`api.downloadBlob`.

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Barcode, Download, Printer, QrCode, Search } from "lucide-react";

import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface ProductRow {
  id: string;
  name: string;
  sku: string;
  barcode?: string | null;
  sell_price?: string | number | null;
}

interface LabelSizeOut {
  key: "38x25" | "50x30" | "a4";
  label_width_mm: number;
  label_height_mm: number;
  labels_per_sheet: number;
}

type BarcodeFormat = "code128" | "qr";

export function LabelPrinter({ currency = "kr" }: { currency?: string }) {
  const t = useTranslations("labels");

  const [products, setProducts] = useState<ProductRow[]>([]);
  const [sizes, setSizes]       = useState<LabelSizeOut[]>([]);
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch]     = useState("");

  // Print options.
  const [size, setSize]               = useState<LabelSizeOut["key"]>("50x30");
  const [format, setFormat]           = useState<BarcodeFormat>("code128");
  const [showPrice, setShowPrice]     = useState(true);
  const [copies, setCopies]           = useState(1);
  const [submitting, setSubmitting]   = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<ProductRow[]>("/api/inventory/products"),
      api.get<LabelSizeOut[]>("/api/labels/sizes"),
    ])
      .then(([p, s]) => { setProducts(p); setSizes(s); })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q) ||
        (p.barcode ?? "").toLowerCase().includes(q),
    );
  }, [products, search]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAll = () => {
    if (selected.size === filtered.length) setSelected(new Set());
    else setSelected(new Set(filtered.map((p) => p.id)));
  };

  const activeSize = sizes.find((s) => s.key === size);
  const totalLabels = selected.size * Math.max(1, copies);
  const sheetsNeeded = activeSize && activeSize.labels_per_sheet > 0
    ? Math.ceil(totalLabels / activeSize.labels_per_sheet)
    : totalLabels;

  async function handlePrint() {
    if (selected.size === 0) {
      toast.error(t("selectAtLeastOne"));
      return;
    }
    setSubmitting(true);
    try {
      await api.downloadBlob(
        "/api/labels/print",
        `labels-${size}.pdf`,
        "POST",
        {
          product_ids: Array.from(selected),
          size,
          format,
          show_price: showPrice,
          currency,
          copies_per_product: Math.max(1, copies),
        },
      );
      toast.success(t("printed", { count: totalLabels }));
    } catch {
      // Error toast already surfaced by downloadBlob.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Options panel ──────────────────────────────────────────── */}
      <div className="vf-section p-5 space-y-4" style={{ borderRadius: 14 }}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* Size */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-2">
              {t("size")}
            </label>
            <select
              value={size}
              onChange={(e) => setSize(e.target.value as LabelSizeOut["key"])}
              className="vf-input text-xs w-full"
            >
              {sizes.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.key} ({s.label_width_mm}×{s.label_height_mm}mm
                  {s.labels_per_sheet > 1 ? `, ${s.labels_per_sheet}/sheet` : ""})
                </option>
              ))}
            </select>
          </div>

          {/* Format */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-2">
              {t("format")}
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setFormat("code128")}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-colors",
                  format === "code128"
                    ? "bg-indigo-500 text-white"
                    : "vf-section vf-text-2 hover:bg-[var(--vf-bg-elevated)]",
                )}
              >
                <Barcode className="h-3.5 w-3.5" /> Code128
              </button>
              <button
                type="button"
                onClick={() => setFormat("qr")}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-colors",
                  format === "qr"
                    ? "bg-indigo-500 text-white"
                    : "vf-section vf-text-2 hover:bg-[var(--vf-bg-elevated)]",
                )}
              >
                <QrCode className="h-3.5 w-3.5" /> QR
              </button>
            </div>
          </div>

          {/* Copies */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-2">
              {t("copies")}
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={copies}
              onChange={(e) => setCopies(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
              className="vf-input text-xs w-full"
            />
          </div>

          {/* Show price */}
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showPrice}
                onChange={(e) => setShowPrice(e.target.checked)}
                className="h-4 w-4 rounded"
              />
              <span className="text-xs font-semibold vf-text-2">{t("showPrice")}</span>
            </label>
          </div>
        </div>

        {/* Summary + print CTA */}
        <div className="flex items-center justify-between pt-2 border-t border-[var(--vf-divider)]">
          <div className="text-xs vf-text-m">
            {t("summary", {
              selected: selected.size,
              labels: totalLabels,
              sheets: sheetsNeeded,
            })}
          </div>
          <button
            type="button"
            onClick={handlePrint}
            disabled={submitting || selected.size === 0}
            className="vf-btn text-xs"
            style={{ minWidth: 140 }}
          >
            {submitting ? (
              <>
                <Download className="h-3.5 w-3.5 animate-pulse" />
                {t("generating")}
              </>
            ) : (
              <>
                <Printer className="h-3.5 w-3.5" />
                {t("print")}
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Product picker ─────────────────────────────────────────── */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("selectProducts")}</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 vf-text-m pointer-events-none" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="vf-input text-xs pl-8 w-64"
              style={{ height: 34 }}
            />
          </div>
        </div>

        {loading ? (
          <div className="py-10 text-center text-xs vf-text-m">{t("loading")}</div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-xs vf-text-m">{t("noProducts")}</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--vf-border)", background: "var(--vf-bg-elevated)" }}>
                <th className="px-5 py-3 text-left w-10">
                  <input
                    type="checkbox"
                    checked={filtered.length > 0 && selected.size === filtered.length}
                    onChange={toggleAll}
                    className="h-4 w-4 rounded"
                  />
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("product")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("sku")}</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden md:table-cell">{t("barcode")}</th>
                <th className="px-5 py-3 text-right text-[11px] font-semibold uppercase tracking-wide vf-text-m">{t("price")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr
                  key={p.id}
                  className="vf-row cursor-pointer"
                  style={{ borderBottom: "1px solid var(--vf-divider)" }}
                  onClick={() => toggle(p.id)}
                >
                  <td className="px-5 py-3.5">
                    <input
                      type="checkbox"
                      checked={selected.has(p.id)}
                      onChange={() => toggle(p.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="h-4 w-4 rounded"
                    />
                  </td>
                  <td className="px-5 py-3.5 vf-text-1 font-medium">{p.name}</td>
                  <td className="px-5 py-3.5 vf-text-2 font-mono text-xs">{p.sku}</td>
                  <td className="px-5 py-3.5 vf-text-m font-mono text-xs hidden md:table-cell">
                    {p.barcode || "—"}
                  </td>
                  <td className="px-5 py-3.5 text-right tabular-nums vf-text-2">
                    {p.sell_price != null ? `${Number(p.sell_price).toFixed(2)} ${currency}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
