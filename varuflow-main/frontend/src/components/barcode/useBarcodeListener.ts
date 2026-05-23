import { useCallback, useEffect, useRef } from "react";

const SCANNER_MAX_INTERVAL_MS = 60;  // hardware scanners type faster than this
const MIN_BARCODE_LENGTH = 4;        // shorter strings are noise

interface Options {
  /** Fire when a scanned barcode is detected. */
  onScan: (barcode: string) => void;
  /** Only fire when this input is focused (pass the input ref). Leave
   *  undefined to listen globally (e.g. POS page). */
  inputRef?: React.RefObject<HTMLInputElement | null>;
  /** Set false to disable the listener without unmounting. */
  enabled?: boolean;
}

/**
 * Detects USB / Bluetooth hardware barcode-scanner input.
 *
 * Hardware scanners emit keystrokes very rapidly (< 60 ms apart) and
 * finish with an Enter key. Human typing is much slower (~150 ms+).
 * This hook collects characters that arrive within the threshold and
 * fires `onScan` when the sequence is complete, rather than letting
 * every character fire a change event on its own.
 *
 * When `inputRef` is supplied the hook only fires when that element is
 * focused; otherwise it listens globally (useful for the full-screen
 * POS where the cashier scans without clicking anything first).
 */
export function useBarcodeListener({ onScan, inputRef, enabled = true }: Options) {
  const buffer = useRef<string>("");
  const lastKeyTime = useRef<number>(0);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    const code = buffer.current.trim();
    buffer.current = "";
    if (code.length >= MIN_BARCODE_LENGTH) onScan(code);
  }, [onScan]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled) return;

      // When inputRef is given, only respond if that element is focused.
      if (inputRef?.current && document.activeElement !== inputRef.current) return;

      const now = Date.now();
      const gap = now - lastKeyTime.current;
      lastKeyTime.current = now;

      if (e.key === "Enter" || e.key === "Tab") {
        if (flushTimer.current) clearTimeout(flushTimer.current);
        flush();
        return;
      }

      // New scan starts: gap since last key exceeds threshold → reset buffer.
      if (gap > SCANNER_MAX_INTERVAL_MS && buffer.current.length > 0) {
        buffer.current = "";
      }

      // Only collect printable single characters (ignore Shift, Ctrl, etc.)
      if (e.key.length === 1) {
        buffer.current += e.key;
      }

      // Auto-flush after 100 ms in case scanner sends no terminator.
      if (flushTimer.current) clearTimeout(flushTimer.current);
      flushTimer.current = setTimeout(flush, 100);
    },
    [enabled, inputRef, flush],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (flushTimer.current) clearTimeout(flushTimer.current);
    };
  }, [handleKeyDown]);
}
