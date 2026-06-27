"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  // Follow the app theme so toasts are readable in dark mode instead of being
  // hardcoded light. resolvedTheme collapses "system" to the concrete value.
  const { resolvedTheme } = useTheme();

  return (
    <Sonner
      theme={(resolvedTheme as ToasterProps["theme"]) ?? "system"}
      className="toaster group"
      toastOptions={{
        // Use --vf-* tokens so the toast surface flips with light/dark instead
        // of being pinned to white/gray.
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-[var(--vf-bg-surface)] group-[.toaster]:text-[var(--vf-text-primary)] group-[.toaster]:border-[var(--vf-border)] group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-[var(--vf-text-muted)]",
          actionButton:
            "group-[.toast]:bg-[var(--vf-brand-primary)] group-[.toast]:text-white",
          cancelButton:
            "group-[.toast]:bg-[var(--vf-bg-elevated)] group-[.toast]:text-[var(--vf-text-secondary)]",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
