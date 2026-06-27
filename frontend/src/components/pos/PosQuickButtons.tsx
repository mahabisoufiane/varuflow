"use client";

/** Quick-button presets — coloured shortcut keys for frequently-sold items.
 *  Cashiers configure these once; during a busy shift they never have to
 *  search for "Mjölk 1L" — one tap adds it to the cart.
 *
 *  The backend holds the ordered list in `pos_quick_buttons` with a
 *  `(org_id, position)` unique constraint so drag-reorder is safe. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePos, type PosProduct } from "@/lib/pos-store";

interface QuickButton {
  id: string;
  product_id: string;
  label: string;
  color: string | null;
  quantity: number;
  position: number;
}

const DEFAULT_COLOR = "#059669"; // emerald-600

export default function PosQuickButtons() {
  const t = useTranslations("pos");
  const { addToCart } = usePos();

  const [buttons, setButtons] = useState<QuickButton[]>([]);
  const [products, setProducts] = useState<Record<string, PosProduct>>({});
  const [managing, setManaging] = useState(false);
  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState<PosProduct[]>([]);
  const [addLabel, setAddLabel] = useState("");
  const [addColor, setAddColor] = useState(DEFAULT_COLOR);
  const [addQty, setAddQty] = useState(1);
  const [addTarget, setAddTarget] = useState<PosProduct | null>(null);
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const [btns, prods] = await Promise.all([
        api.get<QuickButton[]>("/api/pos/quick-buttons"),
        api.get<PosProduct[]>("/api/pos/products"),
      ]);
      setButtons(btns.sort((a, b) => a.position - b.position));
      const map: Record<string, PosProduct> = {};
      for (const p of prods) map[p.id] = p;
      setProducts(map);
    } catch {
      // fail silently — quick buttons are a convenience feature
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function searchProducts(q: string) {
    setAddQuery(q);
    setAddTarget(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { setAddResults([]); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const list = await api.get<PosProduct[]>(
          `/api/pos/products?q=${encodeURIComponent(q.trim())}`,
        );
        setAddResults(list.slice(0, 8));
      } catch { setAddResults([]); }
    }, 250);
  }

  async function handleAdd() {
    if (!addTarget) return;
    setSaving(true);
    try {
      await api.post<QuickButton>("/api/pos/quick-buttons", {
        product_id: addTarget.id,
        label: addLabel || addTarget.name.slice(0, 40),
        color: addColor,
        quantity: addQty,
      });
      setAddTarget(null);
      setAddQuery("");
      setAddLabel("");
      setAddQty(1);
      setAddColor(DEFAULT_COLOR);
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete<void>(`/api/pos/quick-buttons/${id}`);
      setButtons((prev) => prev.filter((b) => b.id !== id));
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (buttons.length === 0 && !managing) return null;

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1" data-testid="pos-quick-buttons">
      {buttons.map((btn) => {
        const product = products[btn.product_id];
        return (
          <button
            key={btn.id}
            type="button"
            disabled={!product}
            onClick={() => {
              if (!product) return;
              addToCart(product, btn.quantity);
            }}
            style={{ borderColor: btn.color ?? DEFAULT_COLOR }}
            className="flex h-12 shrink-0 items-center gap-1.5 rounded-xl border-2 bg-white px-3 text-sm font-semibold transition active:scale-95 disabled:opacity-40 dark:bg-gray-700 dark:text-gray-100"
          >
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: btn.color ?? DEFAULT_COLOR }}
            />
            {btn.label}
            {btn.quantity > 1 && (
              <span className="ml-0.5 rounded bg-gray-100 px-1 text-xs text-gray-600 dark:bg-gray-600 dark:text-gray-300">
                ×{btn.quantity}
              </span>
            )}
          </button>
        );
      })}

      {/* Manage button */}
      <button
        type="button"
        onClick={() => setManaging(true)}
        className="flex h-12 shrink-0 items-center gap-1 rounded-xl border border-dashed border-gray-300 px-3 text-sm text-gray-400 hover:border-gray-400 hover:text-gray-600 dark:border-gray-600 dark:text-gray-500"
        title={t("quick_buttons_manage")}
      >
        ⚙ {buttons.length === 0 ? t("quick_buttons_add_first") : ""}
      </button>

      {/* Management modal */}
      {managing && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl dark:bg-gray-800">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold dark:text-gray-100">{t("quick_buttons_manage")}</h3>
              <button type="button" onClick={() => setManaging(false)} className="text-gray-400 dark:text-gray-500">✕</button>
            </div>

            {/* Existing buttons list */}
            {buttons.length > 0 && (
              <ul className="mb-4 space-y-1">
                {buttons.map((btn) => (
                  <li key={btn.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-700">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: btn.color ?? DEFAULT_COLOR }} />
                      <span className="text-sm dark:text-gray-200">{btn.label}</span>
                      <span className="text-xs text-gray-400 dark:text-gray-500">×{btn.quantity}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDelete(btn.id)}
                      className="text-red-400 hover:text-red-600"
                      aria-label="delete"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {/* Add new button form */}
            <div className="space-y-2 border-t border-gray-100 pt-3 dark:border-gray-700">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">{t("quick_buttons_add")}</p>
              <div className="relative">
                <input
                  type="search"
                  value={addQuery}
                  onChange={(e) => searchProducts(e.target.value)}
                  placeholder={t("search_placeholder")}
                  className="h-10 w-full rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                />
                {addResults.length > 0 && !addTarget && (
                  <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-40 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-600 dark:bg-gray-800">
                    {addResults.map((p) => (
                      <li key={p.id}>
                        <button
                          type="button"
                          onClick={() => { setAddTarget(p); setAddLabel(p.name.slice(0, 40)); setAddResults([]); setAddQuery(p.name); }}
                          className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-100"
                        >
                          {p.name}
                          <span className="ml-2 text-xs text-gray-400">{Number(p.sell_price).toFixed(2)}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {addTarget && (
                <>
                  <input
                    type="text"
                    value={addLabel}
                    onChange={(e) => setAddLabel(e.target.value.slice(0, 40))}
                    placeholder={t("quick_buttons_label")}
                    maxLength={40}
                    className="h-10 w-full rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                  />
                  <div className="flex gap-2">
                    <div className="flex flex-1 items-center gap-2">
                      <label className="text-xs text-gray-500 dark:text-gray-400">{t("quick_buttons_color")}</label>
                      <input type="color" value={addColor} onChange={(e) => setAddColor(e.target.value)} className="h-8 w-10 cursor-pointer rounded" />
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-500 dark:text-gray-400">Qty</label>
                      <input
                        type="number"
                        min={1}
                        value={addQty}
                        onChange={(e) => setAddQty(Math.max(1, Number(e.target.value) || 1))}
                        className="h-8 w-16 rounded border border-gray-300 px-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleAdd}
                    disabled={saving}
                    className="h-10 w-full rounded-lg bg-emerald-600 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {saving ? "…" : t("quick_buttons_save")}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
