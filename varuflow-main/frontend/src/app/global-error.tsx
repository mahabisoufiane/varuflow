"use client";

/**
 * Global error boundary — renders when an uncaught error bubbles up
 * through a React tree that's inside a (locale) segment.
 *
 * Keeps the user out of a blank screen and gives them a single "try again"
 * button instead. Never exposes stack traces.
 */
import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Report to the browser console so Sentry's console breadcrumb catches it.
    // The actual exception is already sent by Sentry's global error handler.
    // Do NOT log the full error object — it may contain PII from props.
    if (process.env.NODE_ENV !== "production") {
      console.error("Global error boundary:", error.message);
    }
  }, [error]);

  return (
    <html>
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
          <AlertTriangle className="mb-4 h-10 w-10 text-amber-500" />
          <h1 className="mb-2 text-xl font-semibold">Something went wrong</h1>
          <p className="mb-6 max-w-md text-sm text-muted-foreground">
            We&apos;re sorry — an unexpected error occurred. Our team has been
            notified. Please try again.
          </p>
          {error.digest && (
            <p className="mb-4 font-mono text-xs opacity-60">
              Reference: {error.digest}
            </p>
          )}
          <button
            type="button"
            onClick={reset}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
