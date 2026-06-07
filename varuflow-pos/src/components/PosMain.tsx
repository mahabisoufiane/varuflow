import { useRef, useState, useEffect } from "react";
import { PosProvider, usePos } from "../lib/pos-store";
import { usePosT } from "../lib/i18n";
import { startSyncListener, replayQueue } from "../lib/sync";
import { countQueued } from "../lib/offline-db";
import { clearToken } from "../lib/auth";
import PosProductGrid from "./PosProductGrid";
import PosCartPanel from "./PosCartPanel";
import PosReceiptModal from "./PosReceiptModal";
import PosSessionControls from "./PosSessionControls";
import PosQuickButtons from "./PosQuickButtons";
import { usePosKeyboard } from "./usePosKeyboard";
import { toast } from "sonner";

function PosScreen() {
  const t = usePosT();
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [queued, setQueued] = useState(0);
  const [online, setOnline] = useState(navigator.onLine);
  const { submitSale, cart, session, lastSale } = usePos();

  useEffect(() => {
    const stopSync = startSyncListener();
    // Replay any queued mutations immediately on mount
    if (navigator.onLine) replayQueue().catch(() => {});

    const updateStatus = () => {
      setOnline(navigator.onLine);
      countQueued().then(setQueued).catch(() => {});
    };
    window.addEventListener("online", updateStatus);
    window.addEventListener("offline", updateStatus);
    updateStatus();
    return () => {
      stopSync();
      window.removeEventListener("online", updateStatus);
      window.removeEventListener("offline", updateStatus);
    };
  }, []);

  usePosKeyboard({
    searchRef,
    onCompleteSale: async () => {
      if (cart.length === 0 || !session) return;
      try { await submitSale(); } catch (e) { toast.error((e as Error).message); }
    },
    onToggleSession: () => {
      document.querySelector<HTMLButtonElement>('[data-testid="pos-close-session"]')?.click();
    },
  });

  return (
    <div className="flex h-screen flex-col gap-3 bg-gray-50 dark:bg-gray-900 p-3">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold dark:text-gray-100">Varuflow POS</h1>
          {!online && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              Offline{queued > 0 ? ` · ${queued} queued` : ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <PosSessionControls />
          <button
            type="button"
            onClick={() => { clearToken(); window.location.reload(); }}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-400"
            title="Sign out"
          >
            ⏻
          </button>
        </div>
      </header>

      <PosQuickButtons />

      <section className="grid flex-1 grid-cols-1 gap-3 overflow-hidden md:grid-cols-[60%_40%]">
        <div className="min-h-0"><PosProductGrid searchRef={searchRef} /></div>
        <div className="hidden min-h-0 md:block"><PosCartPanel /></div>
      </section>

      {/* Mobile sticky cart toggle */}
      <button
        type="button"
        onClick={() => setCartOpen((v) => !v)}
        className="fixed bottom-3 left-3 right-3 z-30 flex h-14 items-center justify-between rounded-xl bg-emerald-600 px-4 text-white shadow-lg md:hidden"
      >
        <span className="font-semibold">{cart.reduce((n, it) => n + it.qty, 0)} items</span>
        <span>{t("complete_sale")} →</span>
      </button>

      {cartOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={() => setCartOpen(false)}>
          <div className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-white p-3" onClick={(e) => e.stopPropagation()}>
            <PosCartPanel />
          </div>
        </div>
      )}

      <footer aria-label={t("keyboard_shortcuts")} className="hidden text-xs text-gray-500 dark:text-gray-400 md:flex md:gap-4">
        <span><kbd className="rounded border px-1">/</kbd> search</span>
        <span><kbd className="rounded border px-1">F2</kbd> {t("complete_sale")}</span>
        <span><kbd className="rounded border px-1">F3</kbd> session</span>
        <span><kbd className="rounded border px-1">+ / −</kbd> qty</span>
        <span><kbd className="rounded border px-1">Esc</kbd> clear</span>
      </footer>

      {lastSale && <PosReceiptModal />}
    </div>
  );
}

export default function PosMain() {
  return (
    <PosProvider>
      <PosScreen />
    </PosProvider>
  );
}
