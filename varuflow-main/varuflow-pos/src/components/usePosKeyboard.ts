/** Global keyboard shortcuts for the tablet POS.
 *  Hidden on touch-only devices via the caller (CSS `md:block`). */

import { useEffect, type RefObject } from "react";
import { usePos } from "../lib/pos-store";

interface Args {
  searchRef: RefObject<HTMLInputElement | null>;
  onCompleteSale: () => void;
  onToggleSession: () => void;
}

export function usePosKeyboard({ searchRef, onCompleteSale, onToggleSession }: Args) {
  const { cart, updateQty } = usePos();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isTypingField =
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);

      // "/" or F1 → focus search (even while typing elsewhere)
      if (e.key === "/" || e.key === "F1") {
        // `/` fires inside inputs too — only steal it from non-field elements.
        if (e.key === "/" && isTypingField) return;
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
        return;
      }
      if (e.key === "F2") { e.preventDefault(); onCompleteSale(); return; }
      if (e.key === "F3") { e.preventDefault(); onToggleSession(); return; }
      if (isTypingField) return;

      if ((e.key === "+" || e.key === "-") && cart.length > 0) {
        e.preventDefault();
        const last = cart[cart.length - 1];
        updateQty(last.product.id, last.qty + (e.key === "+" ? 1 : -1));
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cart, updateQty, searchRef, onCompleteSale, onToggleSession]);
}
