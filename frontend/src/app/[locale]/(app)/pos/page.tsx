"use client";

/** Tablet-optimized POS page (Item 10).
 *
 * Layout:
 *   >= md (768 px): two-column grid [60% / 40%] — product grid left,
 *                   sticky cart right.
 *   <  md:           single column — product grid on top, cart
 *                   collapsible bottom sheet.
 *
 * All cart / session / payment state lives in `<PosProvider>` from
 * `@/lib/pos-store`; this file is purely a composition layer. */

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { PosProvider, usePos } from "@/lib/pos-store";
import PosProductGrid from "@/components/pos/PosProductGrid";
import PosCartPanel from "@/components/pos/PosCartPanel";
import PosReceiptModal from "@/components/pos/PosReceiptModal";
import PosSessionControls from "@/components/pos/PosSessionControls";
import PosQuickButtons from "@/components/pos/PosQuickButtons";
import { usePosKeyboard } from "@/components/pos/usePosKeyboard";
import { toast } from "sonner";

function PosScreen() {
  const t = useTranslations("pos");
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const { submitSale, cart, session, lastSale } = usePos();

  usePosKeyboard({
    searchRef,
    onCompleteSale: async () => {
      if (cart.length === 0 || !session) return;
      try {
        await submitSale();
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    onToggleSession: () => {
      // The SessionControls button is the canonical toggle; shortcut
      // just clicks the visible button so accessibility + visual state
      // stay in sync.
      document.querySelector<HTMLButtonElement>(
        '[data-testid="pos-close-session"]',
      )?.click();
    },
  });

  return (
    <div className="flex h-[calc(100vh-64px)] flex-col gap-3 bg-gray-50 p-3 dark:bg-gray-900">
      {/* Standalone POS app banner */}
      <div className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm dark:border-blue-800 dark:bg-blue-950">
        <span className="text-blue-700 dark:text-blue-300">
          <strong>New:</strong> The standalone POS app is available at{" "}
          <a href="http://localhost:3002" target="_blank" rel="noopener noreferrer" className="underline font-medium">
            localhost:3002
          </a>
          {" "}— optimized for tablets with offline support.
        </span>
      </div>

      <header className="flex items-center justify-between">
        <h1 className="text-xl font-bold dark:text-gray-100">POS</h1>
        <PosSessionControls />
      </header>

      {/* Quick-access preset buttons — cashier shortcuts for top-selling items */}
      <PosQuickButtons />

      <section
        className="grid flex-1 grid-cols-1 gap-3 overflow-hidden md:grid-cols-[60%_40%]"
        data-testid="pos-layout"
      >
        <div className="min-h-0" data-testid="pos-left-column">
          <PosProductGrid searchRef={searchRef} />
        </div>
        <div className="hidden min-h-0 md:block" data-testid="pos-right-column">
          <PosCartPanel />
        </div>
      </section>

      {/* Mobile sticky cart summary + bottom sheet */}
      <button
        type="button"
        onClick={() => setCartOpen((v) => !v)}
        className="fixed bottom-3 left-3 right-3 z-30 flex h-14 items-center justify-between rounded-xl bg-emerald-600 px-4 text-white shadow-lg md:hidden"
        data-testid="pos-mobile-cart-toggle"
      >
        <span className="font-semibold">
          {cart.reduce((n, it) => n + it.qty, 0)} items
        </span>
        <span>{t("complete_sale")} →</span>
      </button>
      {cartOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setCartOpen(false)}
        >
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-white p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <PosCartPanel />
          </div>
        </div>
      )}

      {/* Keyboard shortcut hint bar — desktop only */}
      <footer
        aria-label={t("keyboard_shortcuts")}
        className="hidden text-xs text-gray-500 dark:text-gray-400 md:flex md:gap-4"
      >
        <span><kbd className="rounded border px-1 dark:border-gray-600">/</kbd> search</span>
        <span><kbd className="rounded border px-1 dark:border-gray-600">F2</kbd> {t("complete_sale")}</span>
        <span><kbd className="rounded border px-1 dark:border-gray-600">F3</kbd> session</span>
        <span><kbd className="rounded border px-1 dark:border-gray-600">+ / −</kbd> qty</span>
        <span><kbd className="rounded border px-1 dark:border-gray-600">Esc</kbd> clear</span>
      </footer>

      {lastSale && <PosReceiptModal />}
    </div>
  );
}

export default function PosPage() {
  return (
    <PosProvider>
      <PosScreen />
    </PosProvider>
  );
}
