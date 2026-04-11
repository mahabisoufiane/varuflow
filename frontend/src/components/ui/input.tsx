// File: src/components/ui/input.tsx
// Purpose: Global input component — glass style, focus glow, theme-aware
// Used by: Auth pages, forms across the app

import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          // Base
          "flex w-full h-12 px-4 rounded-xl text-sm transition-all duration-200 outline-none",
          // Colors via CSS vars — theme-aware
          "bg-[var(--vf-glass-bg)] border border-[var(--vf-glass-border)]",
          "text-[var(--vf-text-primary)] placeholder:text-[var(--vf-text-muted)]",
          // Focus
          "focus:border-[#6366F1] focus:ring-2 focus:ring-[rgba(99,102,241,0.15)]",
          // Disabled
          "disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
