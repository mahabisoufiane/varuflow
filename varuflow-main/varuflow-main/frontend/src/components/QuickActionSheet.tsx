"use client";

// File: src/components/QuickActionSheet.tsx
// Purpose: Inner content of the mobile quick-actions bottom sheet.
// Shows either the 5-action menu or one of the inline form views
// (stock movement, quick invoice, record payment). SCAN_PRODUCT and
// QUICK_POS_SALE navigate away and don't render inline.
//
// All form submits go through `@/lib/api-client` so they inherit the
// Item 38 offline queue automatically — no extra plumbing.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api-client";
import { QUICK_ACTIONS, type QuickAction, type SheetView } from "@/lib/quick-actions";

interface Props {
  onClose: () => void;
  /** Optional callback to trigger the camera scanner (mounted by parent). */
  onScan?: () => void;
}

interface ProductMini { id: string; name: string; sku: string; }
interface CustomerMini { id: string; company_name: string; }
interface InvoiceMini  { id: string; invoice_number: string; total: string; due_date: string; }

export default function QuickActionSheet({ onClose, onScan }: Props) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const [view, setView] = useState<SheetView>("menu");
  const firstActionRef = useRef<HTMLButtonElement>(null);

  // Auto-focus the first action when the sheet opens (accessibility).
  useEffect(() => {
    if (view === "menu") firstActionRef.current?.focus();
  }, [view]);

  function handleAction(a: QuickAction) {
    if (a.scan) {
      onScan?.();
      return;
    }
    if (a.to) {
      onClose();
      router.push(`/${locale}${a.to}`);
      return;
    }
    if (a.view) setView(a.view);
  }

  if (view !== "menu") {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-2 border-b border-gray-100 p-3">
          <button
            type="button"
            onClick={() => setView("menu")}
            className="flex h-11 items-center gap-1 rounded-lg px-3 text-sm font-medium text-gray-600"
            data-testid="qa-back"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("quickActions.back")}
          </button>
        </div>
        <div className="overflow-y-auto p-4">
          {view === "stock_movement" && <StockMovementForm onDone={onClose} />}
          {view === "quick_invoice" && <QuickInvoiceForm onDone={onClose} />}
          {view === "record_payment" && <RecordPaymentForm onDone={onClose} />}
        </div>
      </div>
    );
  }

  return (
    <div className="p-2">
      <h2 id="qa-title" className="sr-only">{t("quickActions.sheet_title")}</h2>
      <ul className="divide-y divide-gray-100" data-testid="qa-menu">
        {QUICK_ACTIONS.map((a, i) => {
          const Icon = a.icon;
          return (
            <li key={a.id}>
              <button
                ref={i === 0 ? firstActionRef : undefined}
                type="button"
                onClick={() => handleAction(a)}
                aria-label={t(a.labelKey)}
                className="flex w-full min-h-[56px] items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-gray-50"
              >
                <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${a.colorClass}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <span className="text-sm font-medium text-gray-900">{t(a.labelKey)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Inline form: Stock movement ─────────────────────────────────────────────

function StockMovementForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<ProductMini[]>([]);
  const [picked, setPicked] = useState<ProductMini | null>(null);
  const [direction, setDirection] = useState<"IN" | "OUT">("IN");
  const [qty, setQty] = useState(1);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!q.trim() || picked) return;
    const timer = setTimeout(async () => {
      try {
        const list = await api.get<ProductMini[]>(
          `/api/inventory/products?search=${encodeURIComponent(q)}`,
        );
        setResults(list.slice(0, 5));
      } catch { /* silent */ }
    }, 250);
    return () => clearTimeout(timer);
  }, [q, picked]);

  async function submit() {
    if (!picked || qty < 1) return;
    setBusy(true);
    try {
      await api.post("/api/inventory/stock-movements", {
        product_id: picked.id,
        direction,
        quantity: qty,
        note: note || null,
      });
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        toast.success(t("quickActions.offline_queued"));
      } else {
        toast.success(t("quickActions.stock_movement_success"));
      }
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {!picked ? (
        <>
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("pos.search_placeholder")}
            className="h-12 w-full rounded-lg border border-gray-300 px-3"
          />
          {results.length > 0 && (
            <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200">
              {results.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => setPicked(p)}
                    className="block w-full px-3 py-3 text-left hover:bg-gray-50"
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-gray-500">{p.sku}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <>
          <p className="rounded-lg bg-gray-50 p-3 text-sm font-medium">{picked.name}</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setDirection("IN")}
              className={`h-12 rounded-lg border text-sm font-medium ${direction === "IN" ? "border-emerald-600 bg-emerald-600 text-white" : "border-gray-200 bg-white"}`}
            >IN</button>
            <button
              type="button"
              onClick={() => setDirection("OUT")}
              className={`h-12 rounded-lg border text-sm font-medium ${direction === "OUT" ? "border-red-600 bg-red-600 text-white" : "border-gray-200 bg-white"}`}
            >OUT</button>
          </div>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            value={qty}
            onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
            className="h-12 w-full rounded-lg border border-gray-300 px-3"
          />
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-gray-300 p-3 text-sm"
            placeholder="Note…"
          />
          <button
            type="button"
            disabled={busy}
            onClick={submit}
            data-testid="qa-stock-submit"
            className="h-12 w-full rounded-lg bg-emerald-600 font-semibold text-white disabled:bg-gray-300"
          >{busy ? "…" : t("quickActions.submit")}</button>
        </>
      )}
    </div>
  );
}

// ── Inline form: Quick invoice ─────────────────────────────────────────────

function QuickInvoiceForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<CustomerMini[]>([]);
  const [picked, setPicked] = useState<CustomerMini | null>(null);
  const [amount, setAmount] = useState(0);
  const today = new Date();
  const due = new Date(today.getTime() + 30 * 86_400_000).toISOString().slice(0, 10);
  const [dueDate, setDueDate] = useState(due);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!q.trim() || picked) return;
    const timer = setTimeout(async () => {
      try {
        const list = await api.get<CustomerMini[]>(
          `/api/invoicing/customers?search=${encodeURIComponent(q)}`,
        );
        setResults(list.slice(0, 5));
      } catch { /* silent */ }
    }, 250);
    return () => clearTimeout(timer);
  }, [q, picked]);

  async function submit() {
    if (!picked || amount <= 0) return;
    setBusy(true);
    try {
      const inv = await api.post<{ id: string } & Record<string, unknown>>(
        "/api/invoicing/invoices",
        {
          customer_id: picked.id,
          due_date: dueDate,
          notes: note || null,
          line_items: [{
            description: "Quick invoice",
            quantity: 1,
            unit_price: amount,
            tax_rate: 25,
          }],
        },
      );
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        toast.success(t("quickActions.offline_queued"));
      } else {
        toast.success(t("quickActions.invoice_created"), {
          action: {
            label: t("quickActions.open_invoice"),
            onClick: () => router.push(`/${locale}/invoices/${inv.id}`),
          },
        });
      }
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {!picked ? (
        <>
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Customer…"
            className="h-12 w-full rounded-lg border border-gray-300 px-3"
          />
          {results.length > 0 && (
            <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200">
              {results.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => setPicked(c)}
                    className="block w-full px-3 py-3 text-left hover:bg-gray-50"
                  >{c.company_name}</button>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <>
          <p className="rounded-lg bg-gray-50 p-3 text-sm font-medium">{picked.company_name}</p>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={amount || ""}
            onChange={(e) => setAmount(Number(e.target.value) || 0)}
            placeholder="SEK"
            className="h-12 w-full rounded-lg border border-gray-300 px-3"
          />
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="h-12 w-full rounded-lg border border-gray-300 px-3"
          />
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-gray-300 p-3 text-sm"
            placeholder="Note…"
          />
          <button
            type="button"
            disabled={busy}
            onClick={submit}
            data-testid="qa-invoice-submit"
            className="h-12 w-full rounded-lg bg-emerald-600 font-semibold text-white disabled:bg-gray-300"
          >{busy ? "…" : t("quickActions.submit")}</button>
        </>
      )}
    </div>
  );
}

// ── Inline form: Record payment ────────────────────────────────────────────

function RecordPaymentForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations();
  const [invoices, setInvoices] = useState<InvoiceMini[]>([]);
  const [picked, setPicked] = useState<InvoiceMini | null>(null);
  const [method, setMethod] = useState<"CASH" | "CARD" | "BANK">("CARD");
  const [amount, setAmount] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.get<InvoiceMini[]>(
          "/api/invoicing/invoices?status=unpaid&limit=10",
        );
        // Most-overdue first — soonest past due_date wins.
        list.sort((a, b) => a.due_date.localeCompare(b.due_date));
        setInvoices(list);
      } catch { /* silent */ }
    })();
  }, []);

  function pickInvoice(inv: InvoiceMini) {
    setPicked(inv);
    setAmount(Number(inv.total));
  }

  async function submit() {
    if (!picked || amount <= 0) return;
    setBusy(true);
    try {
      await api.post(`/api/invoicing/invoices/${picked.id}/pay`, {
        amount,
        payment_method: method,
      });
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        toast.success(t("quickActions.offline_queued"));
      } else {
        toast.success(t("quickActions.payment_recorded"));
      }
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!picked) {
    return (
      <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200">
        {invoices.length === 0 && <li className="p-3 text-sm text-gray-400">—</li>}
        {invoices.map((i) => (
          <li key={i.id}>
            <button
              type="button"
              onClick={() => pickInvoice(i)}
              className="flex w-full items-center justify-between px-3 py-3 text-left hover:bg-gray-50"
            >
              <div>
                <div className="font-medium">#{i.invoice_number}</div>
                <div className="text-xs text-gray-500">{i.due_date}</div>
              </div>
              <div className="tabular-nums text-sm font-semibold">
                {Number(i.total).toFixed(2)} SEK
              </div>
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-3">
      <p className="rounded-lg bg-gray-50 p-3 text-sm font-medium">#{picked.invoice_number}</p>
      <div className="grid grid-cols-3 gap-2">
        {(["CASH", "CARD", "BANK"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMethod(m)}
            className={`h-12 rounded-lg border text-sm font-medium ${method === m ? "border-emerald-600 bg-emerald-600 text-white" : "border-gray-200 bg-white"}`}
          >{m}</button>
        ))}
      </div>
      <input
        type="number"
        inputMode="decimal"
        min={0}
        value={amount || ""}
        onChange={(e) => setAmount(Number(e.target.value) || 0)}
        className="h-12 w-full rounded-lg border border-gray-300 px-3"
      />
      <button
        type="button"
        disabled={busy}
        onClick={submit}
        data-testid="qa-payment-submit"
        className="h-12 w-full rounded-lg bg-emerald-600 font-semibold text-white disabled:bg-gray-300"
      >{busy ? "…" : t("quickActions.submit")}</button>
    </div>
  );
}
