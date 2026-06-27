import { useCallback, useRef } from "react";

/**
 * Returns an `emit` function that drops duplicate scan codes within `windowMs`.
 * All camera scanners share this hook instead of copy-pasting lastCode/lastTime refs.
 */
export function useScanDeduplicator(windowMs = 2000) {
  const lastCode = useRef("");
  const lastTime = useRef(0);

  return useCallback(
    (code: string, onScan: (c: string) => void) => {
      const now = Date.now();
      if (code === lastCode.current && now - lastTime.current < windowMs) return;
      lastCode.current = code;
      lastTime.current = now;
      onScan(code);
    },
    [windowMs],
  );
}
