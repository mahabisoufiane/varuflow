import { useRef, useState } from "react";
import { usePosT } from "../lib/i18n";
import { toast } from "sonner";
import { api } from "../lib/api";
import { computeTotals, usePos, type PaymentMethod, type PosCustomer } from "../lib/pos-store";
import { User, X, Minus, Plus, Tag } from "lucide-react";

const METHODS: { key: PaymentMethod; icon: string; label: string }[] = [
  { key: "cash",    icon: "💵", label: "Cash"    },
  { key: "card",    icon: "💳", label: "Card"    },
  { key: "swish",   icon: "📱", label: "Swish"   },
  { key: "account", icon: "📋", label: "Account" },
];

function CustomerSearch() {
  const t = usePosT();
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
      } catch { setResults([]); }
    }, 250);
  }

  if (selectedCustomer) {
    return (
      <div className="flex items-center justify-between rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 text-white">
            <User className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="text-xs font-semibold text-emerald-900">{selectedCustomer.company_name}</p>
            {selectedCustomer.org_number && (
              <p className="text-[10px] text-emerald-600">{selectedCustomer.org_number}</p>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setSelectedCustomer(null)}
          className="rounded-full p-1 text-emerald-400 hover:text-emerald-700 hover:bg-emerald-100"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
        <User className="h-3.5 w-3.5" />
      </div>
      <input
        type="search"
        value={query}
        onChange={(e) => search(e.target.value)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={t("customer_search")}
        className="h-10 w-full rounded-xl border border-slate-200 pl-8 pr-3 text-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-100"
      />
      {open && results.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-48 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl">
          {results.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onMouseDown={() => { setSelectedCustomer(c); setQuery(""); setOpen(false); }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-slate-800">{c.company_name}</span>
                {c.org_number && <span className="ml-2 text-xs text-slate-400">{c.org_number}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PosCartPanel() {
  const t = usePosT();
  const {
    cart, paymentMethod, cashTendered, discountType, discountValue,
    submitting, session, selectedCustomer,
    updateQty, removeFromCart, updateLineDiscount, setPaymentMethod,
    setCashTendered, setDiscount, submitSale,
  } = usePos();

  const [expandedLine, setExpandedLine] = useState<string | null>(null);

  const totals = computeTotals(cart, discountType, discountValue);
  const changeDue = paymentMethod === "cash" ? Math.max(0, cashTendered - totals.total) : 0;

  return (
    <div className="flex h-full flex-col" data-testid="pos-cart-panel">
      {/* Cart header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-bold text-slate-700 uppercase tracking-wider">Cart</h2>
        <span className="flex h-6 min-w-[24px] items-center justify-center rounded-full bg-slate-900 px-1.5 text-xs font-bold text-white">
          {cart.reduce((n, it) => n + it.qty, 0)}
        </span>
      </div>

      {/* Customer */}
      <div className="px-4 py-2 border-b border-slate-100">
        <CustomerSearch />
      </div>

      {/* Line items */}
      <ul className="flex-1 overflow-y-auto px-4 py-3 space-y-2" data-testid="pos-cart-items">
        {cart.length === 0 && (
          <li className="flex flex-col items-center justify-center py-10 text-slate-300">
            <div className="mb-2 text-4xl">🛒</div>
            <p className="text-sm font-medium">{t("cart_empty")}</p>
          </li>
        )}
        {cart.map((it) => (
          <li key={it.product.id} className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-semibold text-slate-800">{it.product.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {it.unit_price.toFixed(2)} SEK ea
                  {it.discount_pct > 0 && (
                    <span className="ml-1 font-medium text-amber-600">−{it.discount_pct}%</span>
                  )}
                </p>
              </div>
              <p className="shrink-0 text-sm font-bold text-slate-800">
                {(it.unit_price * it.qty * (1 - it.discount_pct / 100)).toFixed(2)}
              </p>
            </div>

            <div className="mt-2 flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => updateQty(it.product.id, it.qty - 1)}
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-100 active:scale-95"
                aria-label="decrement"
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
              <span className="w-8 text-center text-sm font-bold text-slate-800">{it.qty}</span>
              <button
                type="button"
                onClick={() => updateQty(it.product.id, it.qty + 1)}
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-100 active:scale-95"
                aria-label="increment"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setExpandedLine(expandedLine === it.product.id ? null : it.product.id)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-amber-600"
                title="Line discount"
              >
                <Tag className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => removeFromCart(it.product.id)}
                className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-slate-300 hover:bg-red-50 hover:text-red-500"
                aria-label="remove"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {expandedLine === it.product.id && (
              <div className="mt-2 flex items-center gap-2">
                <label className="text-xs text-slate-500 shrink-0">{t("line_discount")} %</label>
                <input
                  type="number" min={0} max={100}
                  value={it.discount_pct || ""}
                  onChange={(e) => updateLineDiscount(it.product.id, Number(e.target.value) || 0)}
                  className="h-8 w-20 rounded-lg border border-slate-200 px-2 text-sm focus:outline-none focus:border-emerald-400"
                />
              </div>
            )}
          </li>
        ))}
      </ul>

      {/* Totals + payment */}
      <div className="shrink-0 border-t border-slate-100 bg-white px-4 pb-4 pt-3 space-y-3">
        {/* Discount row */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">{t("discount")}</span>
          <div className="flex items-center gap-1">
            <input
              type="number" inputMode="decimal" min={0}
              value={discountValue || ""}
              onChange={(e) => setDiscount(discountType, Number(e.target.value) || 0)}
              className="w-16 rounded-lg border border-slate-200 px-2 py-1 text-right text-sm focus:outline-none focus:border-emerald-400"
            />
            <select
              value={discountType}
              onChange={(e) => setDiscount(e.target.value as "flat" | "pct", discountValue)}
              className="rounded-lg border border-slate-200 px-2 py-1 text-sm focus:outline-none focus:border-emerald-400"
            >
              <option value="flat">SEK</option>
              <option value="pct">%</option>
            </select>
          </div>
        </div>

        {/* Summary lines */}
        <div className="space-y-1 text-sm">
          <div className="flex justify-between text-slate-500">
            <span>{t("subtotal")}</span>
            <span className="tabular-nums">{totals.netSubtotal.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-slate-500">
            <span>{t("vat")}</span>
            <span className="tabular-nums">{totals.vat.toFixed(2)}</span>
          </div>
          <div className="flex justify-between border-t border-slate-100 pt-2 text-lg font-bold text-slate-900">
            <span>{t("total")}</span>
            <span className="tabular-nums" data-testid="pos-total">
              {totals.total.toFixed(2)} <span className="text-sm font-normal text-slate-400">SEK</span>
            </span>
          </div>
        </div>

        {/* Payment method */}
        <div className="grid grid-cols-4 gap-2">
          {METHODS.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setPaymentMethod(m.key)}
              className={`flex flex-col items-center justify-center gap-1 rounded-xl py-3 text-xs font-semibold transition ${
                paymentMethod === m.key
                  ? "bg-slate-900 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              <span className="text-xl leading-none">{m.icon}</span>
              {m.label}
            </button>
          ))}
        </div>

        {/* Account method info */}
        {paymentMethod === "account" && (
          <p className="rounded-xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
            {selectedCustomer
              ? `Invoice will be created for ${selectedCustomer.company_name} — due in 30 days.`
              : "Select a customer above to use account (Fakturakonto)."}
          </p>
        )}

        {/* Cash tendered */}
        {paymentMethod === "cash" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">{t("cash_tendered")}</label>
            <input
              type="number" inputMode="decimal" min={0}
              value={cashTendered || ""}
              onChange={(e) => setCashTendered(Number(e.target.value) || 0)}
              className="h-11 w-full rounded-xl border border-slate-200 px-3 text-sm focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
              data-testid="pos-cash-tendered"
            />
            {cashTendered > 0 && (
              <p className="mt-1 text-right text-sm">
                {t("change_due")}:{" "}
                <span className="font-bold text-emerald-600" data-testid="pos-change">
                  {changeDue.toFixed(2)} SEK
                </span>
              </p>
            )}
          </div>
        )}

        {/* Complete sale CTA */}
        <button
          type="button"
          disabled={cart.length === 0 || submitting || !session || (paymentMethod === "account" && !selectedCustomer)}
          onClick={async () => {
            try { await submitSale(); }
            catch (e) { toast.error((e as Error).message); }
          }}
          data-testid="pos-complete-sale"
          className="h-14 w-full rounded-2xl bg-emerald-500 text-base font-bold text-white shadow-lg shadow-emerald-500/30 transition hover:bg-emerald-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-30"
        >
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Processing…
            </span>
          ) : paymentMethod === "account" ? (
            `Create Invoice · ${totals.total.toFixed(2)} SEK`
          ) : (
            `${t("complete_sale")} · ${totals.total.toFixed(2)} SEK`
          )}
        </button>
      </div>
    </div>
  );
}
