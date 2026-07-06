// File: src/components/ui/vf-field.tsx
// Purpose: Canonical form primitives for Varuflow — use these in all new modals and forms.
//
// Exports:
//   VFLabel    — uppercase muted label above an input
//   VFOptional — teal pill badge for optional fields
//   VFInput    — styled text input
//   VFTextarea — styled textarea
//   VFSelect   — styled native select
//   VFField    — wrapper that composes label + optional badge + input + hint/error

import * as React from "react";
import { cn } from "@/lib/utils";

// ── Label ─────────────────────────────────────────────────────────────────────

export const VFLabel = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, children, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "block text-[11px] font-semibold uppercase tracking-wide text-[var(--vf-text-muted)] mb-1.5",
      className
    )}
    {...props}
  >
    {children}
  </label>
));
VFLabel.displayName = "VFLabel";

// ── Optional badge ────────────────────────────────────────────────────────────

export function VFOptional() {
  return (
    <span className="inline-block ml-1.5 text-[10px] font-medium text-[var(--vf-brand-secondary)] bg-[var(--vf-brand-secondary-subtle)] px-1.5 py-0.5 rounded-full align-middle leading-none">
      optional
    </span>
  );
}

// ── Shared input token classes ────────────────────────────────────────────────

const inputBase =
  "w-full rounded-lg border border-[var(--vf-border)] py-3 px-3 text-[14px] text-[var(--vf-text-primary)] " +
  "bg-white outline-none transition-all " +
  "focus:ring-2 focus:ring-[var(--vf-brand-primary)] focus:border-[var(--vf-brand-primary)] " +
  "placeholder:text-[13px] placeholder:text-[var(--vf-text-placeholder)] " +
  "disabled:cursor-not-allowed disabled:opacity-50";

// ── VFInput ───────────────────────────────────────────────────────────────────

export const VFInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(inputBase, className)} {...props} />
));
VFInput.displayName = "VFInput";

// ── VFTextarea ────────────────────────────────────────────────────────────────

export const VFTextarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(inputBase, "resize-y min-h-[80px]", className)}
    {...props}
  />
));
VFTextarea.displayName = "VFTextarea";

// ── VFSelect ──────────────────────────────────────────────────────────────────

export const VFSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      inputBase,
      "appearance-none cursor-pointer",
      // Chevron via inline SVG background image
      "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2216%22%20height%3D%2216%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2364748B%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%2F%3E%3C%2Fsvg%3E')]",
      "bg-no-repeat bg-[right_0.75rem_center] pr-10",
      className
    )}
    {...props}
  >
    {children}
  </select>
));
VFSelect.displayName = "VFSelect";

// ── VFField ───────────────────────────────────────────────────────────────────

interface VFFieldProps {
  label: string;
  optional?: boolean;
  hint?: string;
  error?: string;
  htmlFor?: string;
  className?: string;
  children: React.ReactNode;
}

export function VFField({
  label,
  optional,
  hint,
  error,
  htmlFor,
  className,
  children,
}: VFFieldProps) {
  return (
    <div className={cn("flex flex-col", className)}>
      <VFLabel htmlFor={htmlFor}>
        {label}
        {optional && <VFOptional />}
      </VFLabel>
      {children}
      {error && (
        <p className="mt-1.5 text-[12px] text-red-500">{error}</p>
      )}
      {!error && hint && (
        <p className="mt-1.5 text-[12px] text-[var(--vf-text-muted)]">{hint}</p>
      )}
    </div>
  );
}
