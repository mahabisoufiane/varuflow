// File: src/components/ui/button.tsx
// Purpose: Global button component — Varuflow design system with all variants
// Used by: All pages and components across the frontend

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Base: shared across all variants
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6366F1] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] select-none",
  {
    variants: {
      variant: {
        // Indigo gradient — primary CTA
        primary:
          "bg-gradient-to-br from-[#6366F1] to-[#4F46E5] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] hover:from-[#7C7FF5] hover:to-[#5850E6] hover:scale-[1.01] hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.1),0_0_16px_rgba(99,102,241,0.3)]",
        // Glass — secondary action
        secondary:
          "border text-[var(--vf-text-secondary)] hover:text-[var(--vf-text-primary)] hover:scale-[1.01]",
        // Transparent — nav / subtle
        ghost:
          "text-[var(--vf-text-secondary)] hover:bg-[var(--vf-glass-bg)] hover:text-[var(--vf-text-primary)]",
        // Red gradient — destructive action
        danger:
          "bg-gradient-to-br from-[#EF4444] to-[#DC2626] text-white hover:scale-[1.01] hover:shadow-[0_0_16px_rgba(239,68,68,0.3)]",
        // Green gradient — confirm / success
        success:
          "bg-gradient-to-br from-[#10B981] to-[#059669] text-white hover:scale-[1.01] hover:shadow-[0_0_16px_rgba(16,185,129,0.3)]",
        // shadcn compat aliases
        default:
          "bg-gradient-to-br from-[#6366F1] to-[#4F46E5] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] hover:from-[#7C7FF5] hover:to-[#5850E6] hover:scale-[1.01]",
        destructive:
          "bg-gradient-to-br from-[#EF4444] to-[#DC2626] text-white hover:scale-[1.01]",
        outline:
          "border text-[var(--vf-text-secondary)] hover:text-[var(--vf-text-primary)]",
        link: "text-[#6366F1] underline-offset-4 hover:underline h-auto px-0 rounded-none",
      },
      size: {
        default: "h-12 px-5 rounded-xl text-sm",
        sm:      "h-9  px-4 rounded-xl text-xs",
        lg:      "h-14 px-6 rounded-xl text-base",
        icon:    "h-10 w-10 rounded-xl",
      },
    },
    compoundVariants: [
      // Glass border color for secondary/outline in dark mode
      {
        variant: ["secondary", "outline"],
        className: "border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.05)]",
      },
    ],
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading...
          </>
        ) : (
          children
        )}
      </Comp>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
