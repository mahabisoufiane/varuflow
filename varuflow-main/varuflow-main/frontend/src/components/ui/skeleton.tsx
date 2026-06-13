// File: src/components/ui/skeleton.tsx
// Purpose: Animated loading placeholder — drop-in for any content that is loading
// Used by: dashboard, inventory, analytics, customers pages

import { cn } from "@/lib/utils";

/** Renders an animated shimmer box as a content placeholder while data loads. */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("skeleton", className)}
      {...props}
    />
  );
}

export { Skeleton };
