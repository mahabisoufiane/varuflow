"use client";

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
import { LogOut } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

function CashierScreen() {
  const t = useTranslations("pos");
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const { submitSale, cart, session, lastSale } = usePos();
  const router = useRouter();
  const locale = useLocale();
  const supabase = createClient();

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
      document.querySelector<HTMLButtonElement>(
        '[data-testid="pos-close-session"]',
      )?.click();
    },
  });

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/auth/login");
  }

  return (
    <div className="flex h-screen flex-col bg-gray-900 text-gray-100">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-700 px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600">
            <span className="text-xs font-bold text-white">POS</span>
          </div>
          <h1 className="text-lg font-bold">Cash Register</h1>
        </div>
        <div className="flex items-center gap-3">
          <PosSessionControls />
          <button
            onClick={handleSignOut}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </header>

      <PosQuickButtons />

      <section className="grid flex-1 grid-cols-1 gap-0 overflow-hidden md:grid-cols-[1fr_380px]">
        <div className="min-h-0 overflow-hidden border-r border-gray-700">
          <PosProductGrid searchRef={searchRef} />
        </div>
        <div className="hidden min-h-0 overflow-y-auto md:block">
          <PosCartPanel />
        </div>
      </section>

      {/* Mobile cart toggle */}
      <button
        type="button"
        onClick={() => setCartOpen((v) => !v)}
        className="fixed bottom-3 left-3 right-3 z-30 flex h-14 items-center justify-between rounded-xl bg-emerald-600 px-4 text-white shadow-lg md:hidden"
      >
        <span className="font-semibold">
          {cart.reduce((n, it) => n + it.qty, 0)} items
        </span>
        <span>{t("complete_sale")} →</span>
      </button>
      {cartOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={() => setCartOpen(false)}
        >
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-gray-800 p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <PosCartPanel />
          </div>
        </div>
      )}

      {/* Keyboard hints */}
      <footer className="hidden h-8 items-center gap-4 border-t border-gray-700 px-4 text-xs text-gray-500 md:flex">
        <span><kbd className="rounded border border-gray-600 px-1">/</kbd> search</span>
        <span><kbd className="rounded border border-gray-600 px-1">F2</kbd> {t("complete_sale")}</span>
        <span><kbd className="rounded border border-gray-600 px-1">F3</kbd> session</span>
        <span><kbd className="rounded border border-gray-600 px-1">+ / −</kbd> qty</span>
        <span><kbd className="rounded border border-gray-600 px-1">Esc</kbd> clear</span>
      </footer>

      {lastSale && <PosReceiptModal />}
    </div>
  );
}

export default function CashierRegisterPage() {
  return (
    <PosProvider>
      <CashierScreen />
    </PosProvider>
  );
}
