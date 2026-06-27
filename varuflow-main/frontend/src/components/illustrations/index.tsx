// File: src/components/illustrations/index.tsx
// Purpose: On-brand, hand-authored SVG illustrations (no binary assets). Flat,
//   gradient style using the Varuflow indigo/violet palette so they read on
//   both light and dark themes. Decorative only — marked aria-hidden.
//
// Each illustration is a self-contained <svg> with unique gradient ids (so
// several can render on one page without clashing). Sized to a 240×180 box and
// scaled by the container (e.g. EmptyState gives them ~200px width).

import * as React from "react";

type Props = { className?: string };

const base = "h-auto w-full";

/** Empty inventory — an isometric box with a floating package + accent dots. */
export function EmptyInventory({ className }: Props) {
  return (
    <svg viewBox="0 0 240 180" fill="none" role="img" aria-hidden="true" className={className ?? base}>
      <defs>
        <linearGradient id="vfBoxL" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#A5B4FC" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
        <linearGradient id="vfBoxR" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#4338CA" />
        </linearGradient>
      </defs>
      <ellipse cx="120" cy="152" rx="84" ry="13" fill="#2563EB" opacity="0.12" />
      <circle cx="44" cy="46" r="5" fill="#34D399" opacity="0.7" />
      <circle cx="198" cy="38" r="7" fill="#A78BFA" opacity="0.5" />
      <circle cx="208" cy="96" r="4" fill="#2563EB" opacity="0.5" />
      <circle cx="38" cy="104" r="4" fill="#A78BFA" opacity="0.45" />
      {/* small package floating above */}
      <rect x="103" y="26" width="34" height="28" rx="5" fill="#fff" fillOpacity="0.94" />
      <path d="M120 26 V54" stroke="#C7D2FE" strokeWidth="2.5" />
      <path d="M103 40 H137" stroke="#C7D2FE" strokeWidth="2.5" />
      {/* box body */}
      <path d="M70 80 L120 98 V152 L70 134 Z" fill="url(#vfBoxL)" />
      <path d="M170 80 L120 98 V152 L170 134 Z" fill="url(#vfBoxR)" />
      {/* lid */}
      <path d="M70 80 L120 62 L170 80 L120 98 Z" fill="#C7D2FE" />
      <path d="M120 62 V98" stroke="#fff" strokeOpacity="0.6" strokeWidth="2" />
    </svg>
  );
}

/** Empty invoices — a document with lines, a folded corner + a paid badge. */
export function EmptyInvoices({ className }: Props) {
  return (
    <svg viewBox="0 0 240 180" fill="none" role="img" aria-hidden="true" className={className ?? base}>
      <defs>
        <linearGradient id="vfDoc" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#EEF2FF" />
          <stop offset="100%" stopColor="#C7D2FE" />
        </linearGradient>
      </defs>
      <ellipse cx="120" cy="156" rx="78" ry="12" fill="#2563EB" opacity="0.12" />
      <circle cx="52" cy="40" r="6" fill="#A78BFA" opacity="0.5" />
      <circle cx="196" cy="52" r="5" fill="#34D399" opacity="0.65" />
      <circle cx="44" cy="118" r="4" fill="#2563EB" opacity="0.45" />
      {/* document */}
      <path d="M84 34 H146 L168 56 V150 H84 Z" fill="url(#vfDoc)" />
      <path d="M146 34 V56 H168 Z" fill="#A5B4FC" />
      {/* text lines */}
      <rect x="98" y="72" width="56" height="6" rx="3" fill="#60A5FA" opacity="0.9" />
      <rect x="98" y="88" width="40" height="5" rx="2.5" fill="#A5B4FC" />
      <rect x="98" y="100" width="46" height="5" rx="2.5" fill="#A5B4FC" />
      <rect x="98" y="118" width="30" height="5" rx="2.5" fill="#A5B4FC" />
      {/* paid badge */}
      <circle cx="158" cy="132" r="18" fill="#34D399" />
      <path d="M150 132 l6 6 l10 -12" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Empty customers — a card with two avatar chips + detail lines. */
export function EmptyCustomers({ className }: Props) {
  return (
    <svg viewBox="0 0 240 180" fill="none" role="img" aria-hidden="true" className={className ?? base}>
      <defs>
        <linearGradient id="vfCardC" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#312E81" />
          <stop offset="100%" stopColor="#1E1B4B" />
        </linearGradient>
        <linearGradient id="vfAv1" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#60A5FA" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
        <linearGradient id="vfAv2" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#34D399" />
          <stop offset="100%" stopColor="#10B981" />
        </linearGradient>
      </defs>
      <ellipse cx="120" cy="154" rx="80" ry="12" fill="#2563EB" opacity="0.12" />
      <circle cx="46" cy="44" r="6" fill="#A78BFA" opacity="0.5" />
      <circle cx="198" cy="40" r="5" fill="#34D399" opacity="0.6" />
      {/* back card */}
      <rect x="74" y="58" width="92" height="62" rx="12" fill="#2563EB" opacity="0.18" transform="rotate(-6 120 90)" />
      {/* front card */}
      <rect x="66" y="64" width="108" height="66" rx="12" fill="url(#vfCardC)" />
      {/* avatars */}
      <circle cx="92" cy="92" r="15" fill="url(#vfAv1)" />
      <circle cx="118" cy="92" r="15" fill="url(#vfAv2)" />
      {/* detail lines */}
      <rect x="84" y="114" width="72" height="5" rx="2.5" fill="#fff" fillOpacity="0.22" />
      <rect x="98" y="124" width="44" height="4" rx="2" fill="#fff" fillOpacity="0.14" />
    </svg>
  );
}

/** Generic "nothing here" — a soft stage with a magnifier, for search/empty. */
export function EmptyGeneric({ className }: Props) {
  return (
    <svg viewBox="0 0 240 180" fill="none" role="img" aria-hidden="true" className={className ?? base}>
      <defs>
        <linearGradient id="vfRing" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#60A5FA" />
          <stop offset="100%" stopColor="#2563EB" />
        </linearGradient>
      </defs>
      <ellipse cx="120" cy="152" rx="76" ry="12" fill="#2563EB" opacity="0.12" />
      <circle cx="50" cy="48" r="6" fill="#A78BFA" opacity="0.5" />
      <circle cx="192" cy="54" r="5" fill="#34D399" opacity="0.6" />
      <circle cx="110" cy="86" r="38" stroke="url(#vfRing)" strokeWidth="10" fill="none" />
      <path d="M138 114 l24 24" stroke="url(#vfRing)" strokeWidth="11" strokeLinecap="round" />
      <circle cx="110" cy="86" r="20" fill="#2563EB" opacity="0.12" />
    </svg>
  );
}
