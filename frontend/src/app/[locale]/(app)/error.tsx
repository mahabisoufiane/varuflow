"use client";

/**
 * Error boundary for the authenticated (app) segment.
 * Shown when an uncaught exception bubbles up from any page inside
 * the app shell (dashboard, inventory, invoices, etc.).
 */
import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.error("App segment error:", error.message);
    }
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
      <AlertTriangle className="mb-4 h-8 w-8 text-amber-500" />
      <h2 className="mb-2 text-lg font-semibold">This page hit an error</h2>
      <p className="mb-4 max-w-md text-sm text-muted-foreground">
        The rest of the app is still working. You can try reloading this page,
        or navigate elsewhere using the sidebar.
      </p>
      {error.digest && (
        <p className="mb-4 font-mono text-xs opacity-60">
          Reference: {error.digest}
        </p>
      )}
      <button
        type="button"
        onClick={reset}
        className="inline-flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Try again
      </button>
    </div>
  );
}
