"use client";

/** Right column / bottom-sheet on mobile: line items, totals, payment
 *  methods, discount and the Complete-Sale button. Reads all state from
 *  the PosProvider — no local useState for cart fields (per Item 10 rule). */

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { computeTotals, usePos, type PaymentMethod, type PosCustomer } from "@/lib/pos-store";

const METHODS: { key: PaymentMethod; emoji: string; labelKey: string }[] = [
  { key: "cash",  emoji: "💵", labelKey: "payment_cash"  },
  { key: "card",  emoji: "💳", labelKey: "payment_card"  },
  { key: "swish", emoji: "📱", labelKey: "payment_swish" },
];

function CustomerSearch() {
  const t = useTranslations("pos");
  const { selectedCustomer, setSelectedCustomer } = usePos();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PosCustomer[]>([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function search(q: string) {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { setResults([]); setOpen(false); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const list = await api.get<PosCustomer[]>(
          `/api/invoicing/customers?search=${encodeURIComponent(q.trim())}&is_active=true&limit=8`,
        );
        setResults(list);
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 250);
  }

  if (selectedCustomer) {
    return (
      <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2 text-sm dark:bg-emerald-900/30">
        <div>
          <p className="font-medium text-emerald-900 dark:text-emerald-200">{selectedCustomer.company_name}</p>
          {selectedCustomer.org_number && (
            <p className="text-xs text-emerald-700 dark:text-emerald-400">{selectedCustomer.org_number}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setSelectedCustomer(null)}
          className="ml-2 text-emerald-700 hover:text-emerald-900 dark:text-emerald-400"
          aria-label="Remove customer"
        >
          ×
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <input
        type="search"
        value={query}
        onChange={(e) => search(e.target.value)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={t("customer_search")}
        className="h-10 w-full rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
      />
      {open && results.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-600 dark:bg-gray-800">
          {results.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onMouseDown={() => {
                  setSelectedCustomer(c);
                  setQuery("");
                  setOpen(false);
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                <span className="font-medium dark:text-gray-100">{c.company_name}</span>
                {c.org_number && (
                  <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">{c.org_number}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PosCartPanel() {
  const t = useTranslations("pos");
  const {
    cart, paymentMethod, cashTendered, discountType, discountValue,
    submitting, session,
    updateQty, removeFromCart, updateLineDiscount, setPaymentMethod, setCashTendered,
    setDiscount, submitSale,
  } = usePos();

  const [expandedLine, setExpandedLine] = useState<string | null>(null);

  const totals = computeTotals(cart, discountType, discountValue);
  const changeDue =
    paymentMethod === "cash" ? Math.max(0, cashTendered - totals.total) : 0;

  return (
    <aside
      className="flex h-full flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
      data-testid="pos-cart-panel"
    >
      <header className="flex items-baseline justify-between border-b border-gray-100 pb-2 dark:border-gray-700">
        <h2 className="text-lg font-semibold dark:text-gray-100">Kassa</h2>
        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
          {cart.reduce((n, it) => n + it.qty, 0)}
        </span>
      </header>

      {/* Customer selector */}
      <CustomerSearch />

      <ul className="flex-1 space-y-2 overflow-y-auto" data-testid="pos-cart-items">
        {cart.length === 0 && (
          <li className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t("cart_empty")}</li>
        )}
        {cart.map((it) => (
          <li
            key={it.product.id}
            className="rounded-lg bg-gray-50 p-2 dark:bg-gray-700"
          >
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <div>
                <p className="text-sm font-medium dark:text-gray-100">{it.product.name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {it.unit_price.toFixed(2)} × {it.qty}
                  {it.discount_pct > 0 && (
                    <span className="ml-1 text-amber-600 dark:text-amber-400">
                      -{it.discount_pct}%
                    </span>
                  )}
                  {" "}= {(it.unit_price * it.qty * (1 - it.discount_pct / 100)).toFixed(2)} SEK
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => updateQty(it.product.id, it.qty - 1)}
                  className="h-11 w-11 rounded-lg bg-white text-xl font-bold text-gray-700 shadow-sm dark:bg-gray-600 dark:text-gray-100"
                  aria-label="decrement"
                >
                  −
                </button>
                <span className="min-w-[2ch] text-center font-semibold dark:text-gray-100">{it.qty}</span>
                <button
                  type="button"
                  onClick={() => updateQty(it.product.id, it.qty + 1)}
                  className="h-11 w-11 rounded-lg bg-white text-xl font-bold text-gray-700 shadow-sm dark:bg-gray-600 dark:text-gray-100"
                  aria-label="increment"
                >
                  +
                </button>
                <button
                  type="button"
                  onClick={() => setExpandedLine(expandedLine === it.product.id ? null : it.product.id)}
                  className="h-11 w-11 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600"
                  aria-label="line discount"
                  title={t("line_discount")}
                >
                  %
                </button>
                <button
                  type="button"
                  onClick={() => removeFromCart(it.product.id)}
                  className="ml-1 h-11 w-11 rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                  aria-label="remove"
                >
                  ×
                </button>
              </div>
            </div>
            {expandedLine === it.product.id && (
              <div className="mt-2 flex items-center gap-2">
                <label className="text-xs text-gray-500 dark:text-gray-400">{t("line_discount")} %</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={it.discount_pct || ""}
                  onChange={(e) => updateLineDiscount(it.product.id, Number(e.target.value) || 0)}
                  className="h-8 w-20 rounded border border-gray-300 px-2 text-sm dark:border-gray-600 dark:bg-gray-600 dark:text-gray-100"
                />
              </div>
            )}
          </li>
        ))}
      </ul>

      <div className="space-y-2 border-t border-gray-100 pt-3 text-sm dark:border-gray-700">
        <div className="flex items-center justify-between">
          <span className="dark:text-gray-300">{t("discount")}</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              inputMode="decimal"
              min={0}
              value={discountValue || ""}
              onChange={(e) =>
                setDiscount(discountType, Number(e.target.value) || 0)
              }
              className="w-20 rounded border border-gray-300 px-2 py-1 text-right dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
            />
            <select
              value={discountType}
              onChange={(e) =>
                setDiscount(e.target.value as "flat" | "pct", discountValue)
              }
              className="rounded border border-gray-300 px-2 py-1 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
            >
              <option value="flat">SEK</option>
              <option value="pct">%</option>
            </select>
          </div>
        </div>
        <div className="flex justify-between text-gray-600 dark:text-gray-300">
          <span>{t("subtotal")}</span>
          <span className="tabular-nums">{totals.netSubtotal.toFixed(2)} SEK</span>
        </div>
        <div className="flex justify-between text-gray-600 dark:text-gray-300">
          <span>{t("vat")}</span>
          <span className="tabular-nums">{totals.vat.toFixed(2)} SEK</span>
        </div>
        <div className="flex justify-between border-t border-gray-100 pt-2 text-base font-semibold dark:border-gray-700 dark:text-gray-100">
          <span>{t("total")}</span>
          <span className="tabular-nums" data-testid="pos-total">
            {totals.total.toFixed(2)} SEK
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {METHODS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setPaymentMethod(m.key)}
            className={`flex min-h-[56px] flex-col items-center justify-center rounded-lg border text-sm font-medium transition ${
              paymentMethod === m.key
                ? "border-emerald-600 bg-emerald-600 text-white"
                : "border-gray-200 bg-white text-gray-700 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
            }`}
          >
            <span className="text-xl">{m.emoji}</span>
            {t(m.labelKey)}
          </button>
        ))}
      </div>

      {paymentMethod === "cash" && (
        <div className="space-y-1">
          <label className="text-xs text-gray-500 dark:text-gray-400">{t("cash_tendered")}</label>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={cashTendered || ""}
            onChange={(e) => setCashTendered(Number(e.target.value) || 0)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
            data-testid="pos-cash-tendered"
          />
          <p className="text-right text-sm text-gray-600 dark:text-gray-300">
            {t("change_due")}:{" "}
            <span className="font-semibold text-emerald-700 dark:text-emerald-400" data-testid="pos-change">
              {changeDue.toFixed(2)} SEK
            </span>
          </p>
        </div>
      )}

      <button
        type="button"
        disabled={cart.length === 0 || submitting || !session}
        onClick={async () => {
          try {
            await submitSale();
          } catch (e) {
            toast.error((e as Error).message);
          }
        }}
        data-testid="pos-complete-sale"
        className="mt-2 h-14 w-full rounded-xl bg-emerald-600 text-base font-semibold text-white shadow-md transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-gray-300 dark:disabled:bg-gray-600"
      >
        {submitting ? "…" : t("complete_sale")}
      </button>
    </aside>
  );
}
