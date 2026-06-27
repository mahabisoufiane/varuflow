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
import { LogOut, Wifi, WifiOff, ShoppingCart } from "lucide-react";

function PosScreen() {
  const t = usePosT();
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [queued, setQueued] = useState(0);
  const [online, setOnline] = useState(navigator.onLine);
  const { submitSale, cart, session, lastSale } = usePos();

  useEffect(() => {
    const stopSync = startSyncListener();
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

  const cartCount = cart.reduce((n, it) => n + it.qty, 0);

  return (
    <div className="flex h-screen flex-col bg-slate-100">
      {/* ── Top bar ──────────────────────────────────────────────── */}
      <header className="flex h-14 shrink-0 items-center justify-between bg-slate-900 px-4 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 shadow shadow-emerald-500/30">
            <span className="text-sm font-black text-white">V</span>
          </div>
          <span className="text-base font-bold text-white tracking-tight">Varuflow POS</span>
          {!online ? (
            <span className="flex items-center gap-1 rounded-full bg-amber-500/20 px-2.5 py-0.5 text-xs font-semibold text-amber-400">
              <WifiOff className="h-3 w-3" />
              Offline{queued > 0 ? ` · ${queued} queued` : ""}
            </span>
          ) : (
            <span className="flex items-center gap-1 rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-semibold text-emerald-400">
              <Wifi className="h-3 w-3" />
              Online
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <PosSessionControls />
          <button
            type="button"
            onClick={() => { clearToken(); window.location.reload(); }}
            title="Sign out"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-700 hover:text-white transition"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* ── Quick-access buttons ──────────────────────────────────── */}
      <div className="shrink-0 bg-white border-b border-slate-200 px-4 py-2">
        <PosQuickButtons />
      </div>

      {/* ── Main area: product grid + cart ───────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Product grid */}
        <main className="flex-1 min-w-0 overflow-hidden p-4">
          <PosProductGrid searchRef={searchRef} />
        </main>

        {/* Cart — hidden on mobile, visible md+ */}
        <aside className="hidden md:flex w-[360px] shrink-0 flex-col border-l border-slate-200 bg-white">
          <PosCartPanel />
        </aside>
      </div>

      {/* ── Mobile cart FAB ───────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setCartOpen((v) => !v)}
        className="fixed bottom-4 right-4 z-30 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500 shadow-xl shadow-emerald-500/40 md:hidden"
        aria-label="Open cart"
      >
        <ShoppingCart className="h-7 w-7 text-white" />
        {cartCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
            {cartCount}
          </span>
        )}
      </button>

      {/* ── Mobile cart sheet ─────────────────────────────────────── */}
      {cartOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={() => setCartOpen(false)}
        >
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[90vh] overflow-y-auto rounded-t-3xl bg-white"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto my-2 h-1 w-12 rounded-full bg-slate-200" />
            <PosCartPanel />
          </div>
        </div>
      )}

      {/* ── Keyboard shortcuts bar ────────────────────────────────── */}
      <footer aria-label={t("keyboard_shortcuts")} className="hidden bg-slate-800 px-4 py-1.5 md:flex md:gap-5">
        {[
          ["/ ", "search"],
          ["F2", t("complete_sale")],
          ["F3", "session"],
          ["+ / −", "qty"],
          ["Esc", "clear"],
        ].map(([key, label]) => (
          <span key={key} className="flex items-center gap-1.5 text-xs text-slate-400">
            <kbd className="rounded bg-slate-700 px-1.5 py-0.5 font-mono text-slate-200">{key}</kbd>
            {label}
          </span>
        ))}
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
