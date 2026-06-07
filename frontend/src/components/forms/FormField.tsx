"use client";

// File: frontend/src/components/forms/FormField.tsx
// Purpose: Shared touch-friendly form field primitive (Item 15).
//
// One component handles: text, number, decimal, email, tel, url, search,
// password, date, textarea, select, checkbox, toggle. Labels are
// always rendered *above* the input (never placeholder-only), hint
// text sits below the label, error text sits below the control and is
// wired up via aria-describedby + aria-invalid.
//
// Design targets:
//   * min-height 44px on all interactive controls (56px on primary
//     buttons — see MobileFormActions); Tailwind utility `min-h-11`.
//   * full-width inputs on mobile.
//   * red border + aria-invalid="true" on error.
//   * inputMode maps to the semantic `kind` prop so numeric fields get
//     the numeric keypad on phones.

import * as React from "react";
import { inputModeFor } from "@/hooks/useMobileForm";

// ── Types ─────────────────────────────────────────────────────────────

export type FieldKind =
  | "text"
  | "number"
  | "decimal"
  | "email"
  | "tel"
  | "url"
  | "search"
  | "password"
  | "date"
  | "textarea"
  | "select"
  | "checkbox"
  | "toggle";

interface BaseProps {
  id?: string;
  name?: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  icon?: React.ReactNode;
  "data-testid"?: string;
}

interface InputProps extends BaseProps {
  kind?: Exclude<FieldKind, "textarea" | "select" | "checkbox" | "toggle">;
  value?: string | number;
  defaultValue?: string | number;
  onChange?: (value: string) => void;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  autoComplete?: string;
  autoFocus?: boolean;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  pattern?: string;
}

interface TextareaProps extends BaseProps {
  kind: "textarea";
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  rows?: number;
}

interface SelectProps extends BaseProps {
  kind: "select";
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
  placeholder?: string;
}

interface CheckableProps extends BaseProps {
  kind: "checkbox" | "toggle";
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
}

export type FormFieldProps =
  | InputProps
  | TextareaProps
  | SelectProps
  | CheckableProps;

// ── Helpers ───────────────────────────────────────────────────────────

function fieldId(id: string | undefined, name: string | undefined) {
  if (id) return id;
  if (name) return `ff-${name}`;
  // Deterministic fallback is not possible SSR-side without React 18
  // useId, but callers should always pass `id` or `name`.
  return `ff-${Math.random().toString(36).slice(2, 8)}`;
}

// Base classes shared across input-like controls.
const inputBase =
  "w-full min-h-11 rounded-xl border px-3 py-2 text-[15px] md:text-sm " +
  "bg-vf-bg-elevated border-white/10 text-vf-text-primary " +
  "placeholder:text-vf-text-muted " +
  "focus:outline-none focus:ring-2 focus:ring-vf-accent/40 focus:border-vf-accent/60 " +
  "disabled:opacity-60 disabled:cursor-not-allowed transition";

const invalidClasses = "border-vf-danger/70 vf-invalid";

// ── Main component ────────────────────────────────────────────────────

export function FormField(props: FormFieldProps) {
  const resolvedId = fieldId(props.id, props.name);
  const errorId = props.error ? `${resolvedId}-error` : undefined;
  const hintId = props.hint && !props.error ? `${resolvedId}-hint` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const hasError = Boolean(props.error);

  const LabelEl = (
    <label
      htmlFor={resolvedId}
      className="flex items-center gap-1.5 text-xs font-medium text-vf-text-secondary"
    >
      {props.icon && (
        <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center text-vf-text-muted">
          {props.icon}
        </span>
      )}
      <span>{props.label}</span>
      {props.required && <span aria-hidden className="text-vf-danger">*</span>}
    </label>
  );

  const ErrorEl = hasError && (
    <p
      id={errorId}
      role="alert"
      className="text-xs text-vf-danger"
      data-testid={`${props["data-testid"] ?? resolvedId}-error`}
    >
      {props.error}
    </p>
  );

  const HintEl = !hasError && props.hint && (
    <p id={hintId} className="text-xs text-vf-text-muted">
      {props.hint}
    </p>
  );

  // ── Checkbox / Toggle — label is a full-row clickable target ──────
  if (props.kind === "checkbox" || props.kind === "toggle") {
    const { kind, checked, defaultChecked, onChange, disabled } = props;
    return (
      <div className={["space-y-1", props.className].filter(Boolean).join(" ")}>
        <label
          htmlFor={resolvedId}
          className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-2 py-2 hover:bg-white/5"
          data-testid={props["data-testid"]}
        >
          <input
            id={resolvedId}
            type="checkbox"
            role={kind === "toggle" ? "switch" : undefined}
            className={
              kind === "toggle"
                ? "h-6 w-10 shrink-0 appearance-none rounded-full bg-white/10 " +
                  "checked:bg-vf-accent relative transition " +
                  "after:absolute after:top-0.5 after:left-0.5 after:h-5 after:w-5 " +
                  "after:rounded-full after:bg-white after:transition " +
                  "checked:after:translate-x-4"
                : "h-5 w-5 shrink-0 rounded border border-white/20 " +
                  "bg-vf-bg-elevated accent-vf-accent"
            }
            checked={checked}
            defaultChecked={defaultChecked}
            disabled={disabled}
            aria-invalid={hasError || undefined}
            aria-describedby={describedBy}
            onChange={(e) => onChange?.(e.target.checked)}
          />
          <div className="min-w-0 flex-1">
            <span className="block text-sm text-vf-text-primary">{props.label}</span>
            {props.hint && !hasError && (
              <span className="mt-0.5 block text-xs text-vf-text-muted">
                {props.hint}
              </span>
            )}
          </div>
        </label>
        {ErrorEl}
      </div>
    );
  }

  // ── Textarea ──────────────────────────────────────────────────────
  if (props.kind === "textarea") {
    const { value, defaultValue, onChange, placeholder, rows, disabled } = props;
    return (
      <div className={["space-y-1.5", props.className].filter(Boolean).join(" ")}>
        {LabelEl}
        {HintEl}
        <textarea
          id={resolvedId}
          name={props.name}
          value={value}
          defaultValue={defaultValue}
          placeholder={placeholder}
          rows={rows ?? 4}
          disabled={disabled}
          required={props.required}
          aria-invalid={hasError || undefined}
          aria-describedby={describedBy}
          data-testid={props["data-testid"]}
          onChange={(e) => onChange?.(e.target.value)}
          className={[
            inputBase,
            "min-h-24 resize-y leading-relaxed",
            hasError && invalidClasses,
          ]
            .filter(Boolean)
            .join(" ")}
        />
        {ErrorEl}
      </div>
    );
  }

  // ── Select ────────────────────────────────────────────────────────
  if (props.kind === "select") {
    const { value, defaultValue, onChange, options, placeholder, disabled } = props;
    return (
      <div className={["space-y-1.5", props.className].filter(Boolean).join(" ")}>
        {LabelEl}
        {HintEl}
        <select
          id={resolvedId}
          name={props.name}
          value={value}
          defaultValue={defaultValue}
          disabled={disabled}
          required={props.required}
          aria-invalid={hasError || undefined}
          aria-describedby={describedBy}
          data-testid={props["data-testid"]}
          onChange={(e) => onChange?.(e.target.value)}
          className={[inputBase, hasError && invalidClasses].filter(Boolean).join(" ")}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
        {ErrorEl}
      </div>
    );
  }

  // ── Text/Number/Date/etc. ─────────────────────────────────────────
  const inputProps = props as InputProps;
  const kind = inputProps.kind ?? "text";
  const {
    value,
    defaultValue,
    onChange,
    placeholder,
    min,
    max,
    step,
    autoComplete,
    autoFocus,
    pattern,
    disabled,
  } = inputProps;

  // Browser `type` is slightly different from our semantic kind.
  // `decimal` stays `type="text"` because Safari's number input strips
  // the decimal separator on some locales; `inputMode="decimal"` is
  // what actually picks the keypad.
  const htmlType =
    kind === "decimal"
      ? "text"
      : kind === "number"
        ? "number"
        : kind === "search"
          ? "search"
          : kind === "url"
            ? "url"
            : kind === "tel"
              ? "tel"
              : kind === "email"
                ? "email"
                : kind === "password"
                  ? "password"
                  : kind === "date"
                    ? "date"
                    : "text";

  return (
    <div className={["space-y-1.5", props.className].filter(Boolean).join(" ")}>
      {LabelEl}
      {HintEl}
      <div className="relative">
        <input
          id={resolvedId}
          name={props.name}
          type={htmlType}
          value={value as string | number | undefined}
          defaultValue={defaultValue as string | number | undefined}
          placeholder={placeholder}
          disabled={disabled}
          required={props.required}
          min={min}
          max={max}
          step={step}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          inputMode={inputProps.inputMode ?? (kind === "date" || kind === "password" ? undefined : inputModeFor(
            kind as "text" | "number" | "decimal" | "email" | "tel" | "url" | "search",
          ))}
          pattern={
            pattern ?? (kind === "number" ? "[0-9]*" : undefined)
          }
          aria-invalid={hasError || undefined}
          aria-describedby={describedBy}
          data-testid={props["data-testid"]}
          onChange={(e) => onChange?.(e.target.value)}
          className={[inputBase, hasError && invalidClasses].filter(Boolean).join(" ")}
        />
      </div>
      {ErrorEl}
    </div>
  );
}

export default FormField;
