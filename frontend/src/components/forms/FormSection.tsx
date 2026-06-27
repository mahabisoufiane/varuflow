"use client";

// File: frontend/src/components/forms/FormSection.tsx
// Purpose: Bordered card wrapper that groups related FormFields.
// Desktop: bordered surface with padding; mobile: edge-to-edge stack.

import * as React from "react";

export interface FormSectionProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  "data-testid"?: string;
}

export function FormSection({
  title,
  description,
  children,
  className,
  ...rest
}: FormSectionProps) {
  return (
    <section
      data-testid={rest["data-testid"]}
      className={[
        // Edge-to-edge on mobile, bordered card on ≥md.
        "space-y-4 md:space-y-5",
        "md:rounded-2xl md:border md:border-white/10 md:bg-vf-bg-surface md:p-6",
        "py-2",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {(title || description) && (
        <header className="space-y-1">
          {title && (
            <h2 className="text-sm font-semibold text-vf-text-primary md:text-base">
              {title}
            </h2>
          )}
          {description && (
            <p className="text-xs text-vf-text-muted md:text-sm">{description}</p>
          )}
        </header>
      )}
      <div className="space-y-4 md:grid md:grid-cols-2 md:gap-5 md:space-y-0">
        {children}
      </div>
    </section>
  );
}

export default FormSection;
