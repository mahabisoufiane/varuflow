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
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vf-brand-primary)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] select-none",
  {
    variants: {
      variant: {
        // Brand blue — primary CTA
        primary:
          "bg-[var(--vf-brand-primary)] text-white shadow-sm hover:bg-[var(--vf-brand-primary-hover)] hover:shadow-[0_4px_12px_rgba(74,108,247,0.25)]",
        // Glass — secondary action
        secondary:
          "border text-[var(--vf-text-secondary)] hover:text-[var(--vf-text-primary)] hover:scale-[1.01]",
        // Transparent — nav / subtle
        ghost:
          "text-[var(--vf-text-secondary)] hover:bg-[var(--vf-hover)] hover:text-[var(--vf-text-primary)]",
        // Red — destructive action
        danger:
          "bg-[#DC2626] text-white hover:bg-[#B91C1C] hover:shadow-[0_4px_12px_rgba(220,38,38,0.25)]",
        // Green — confirm / success
        success:
          "bg-[#059669] text-white hover:bg-[#047857] hover:shadow-[0_4px_12px_rgba(5,150,105,0.25)]",
        // shadcn compat aliases
        default:
          "bg-[var(--vf-brand-primary)] text-white shadow-sm hover:bg-[var(--vf-brand-primary-hover)] hover:shadow-[0_4px_12px_rgba(74,108,247,0.25)]",
        destructive:
          "bg-[#DC2626] text-white hover:bg-[#B91C1C]",
        outline:
          "border text-[var(--vf-text-secondary)] hover:text-[var(--vf-text-primary)]",
        link: "text-[var(--vf-brand-primary)] underline-offset-4 hover:underline h-auto px-0 rounded-none",
      },
      size: {
        default: "h-12 px-5 rounded-xl text-sm",
        sm:      "h-9  px-4 rounded-xl text-xs",
        lg:      "h-14 px-6 rounded-xl text-base",
        icon:    "h-10 w-10 rounded-xl",
      },
    },
    compoundVariants: [
      {
        variant: ["secondary", "outline"],
        className: "border-[var(--vf-border)] bg-[var(--vf-bg-surface)]",
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
