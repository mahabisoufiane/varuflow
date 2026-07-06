# Design Token Inventory — Phase 1A (read-only audit)

Generated 2026-07-06 by scanning `frontend/src` (731 files: tsx/ts/css/scss).
Quality-gate note: this repo uses **npm** (not pnpm) and `next lint` is currently
broken repo-wide (ESLint 9 flat-config migration pending), so phase gates are
adapted to: `npx tsc --noEmit` + token-check script + `npm run build`.

## 1. Current inventory (the problem, quantified)

| Category | Distinct values | Assessment |
|---|---|---|
| Hex colors | **188** | ~20× too many |
| rgb()/hsl() colors | **197** | mostly in CSS/SCSS token files + shadows |
| Tailwind arbitrary colors (`bg-[#…]`) | **44** | should be 0 |
| Tailwind palette families used | **19 of 22** | should be ~2 (neutral + accent) + semantics |
| Arbitrary font sizes (`text-[13px]`) | 10 | should be 0 |
| Arbitrary radii | 4 | should be 0 |
| Arbitrary shadows | 11 | should be 0 |
| Arbitrary px spacing (`p-[7px]`…) | 42 | should be 0 |

### Palette-family usage (why the app feels color-chaotic)
| Family | Usages |
|---|---|
| `gray` | 4080 |
| `red` | 1065 |
| `green` | 791 |
| `blue` | 701 |
| `indigo` | 572 |
| `amber` | 443 |
| `slate` | 350 |
| `emerald` | 300 |
| `yellow` | 203 |
| `purple` | 152 |
| `orange` | 99 |
| `rose` | 84 |
| `violet` | 44 |
| `teal` | 24 |
| `pink` | 15 |

Three different "blues" (blue / indigo / sky) and three "greens" (green /
emerald / teal) compete as pseudo-accents across pages — no single brand color.

### Top hex values
| Value | Count |
|---|---|
| `#1a2332` | 801 |
| `#2a3342` | 157 |
| `#f3f4f6` | 111 |
| `#dcfce7` | 110 |
| `#dbeafe` | 86 |
| `#1d4ed8` | 85 |
| `#166534` | 81 |
| `#fee2e2` | 71 |
| `#2563eb` | 68 |
| `#4b5563` | 45 |
| `#fef9c3` | 41 |
| `#6b7280` | 40 |

### Top arbitrary Tailwind colors
| Value | Count |
|---|---|
| `ring-[#1a2332]` | 273 |
| `bg-[#1a2332]` | 225 |
| `bg-[#2a3342]` | 155 |
| `border-[#1a2332]` | 126 |
| `text-[#1a2332]` | 119 |
| `from-[#2563EB]` | 8 |
| `to-[#1D4ED8]` | 8 |
| `text-[#2563EB]` | 8 |
| `bg-[#0f172a]` | 6 |
| `text-[#1D4ED8]` | 5 |

### Top offending files
| File | Hardcoded values |
|---|---|
| `src/app/globals.css` | 242 |
| `src/styles/globals.scss` | 143 |
| `src/app/[locale]/onboarding/page.tsx` | 132 |
| `src/app/[locale]/(app)/mobile/routes/page.tsx` | 125 |
| `src/app/[locale]/(app)/hr/training/page.tsx` | 121 |
| `src/app/[locale]/(app)/investor/cap-table/page.tsx` | 119 |
| `src/app/[locale]/(app)/reports/cashflow/page.tsx` | 106 |
| `src/app/[locale]/(app)/ops/decisions/page.tsx` | 106 |
| `src/app/[locale]/(app)/accounting/bank-reconciliation/page.tsx` | 103 |
| `src/app/[locale]/(app)/admin/sequences/page.tsx` | 99 |

### Near-duplicate merge candidates (channel distance ≤ 24)
- `#1a2332` ≈ `#2a3342` ≈ `#1e293b` ≈ `#0f172a` ≈ `#1f2937` ≈ `#1a1d27` ≈ `#22252f` ≈ `#263244` ≈ `#2a2d38`
- `#f3f4f6` ≈ `#dcfce7` ≈ `#dbeafe` ≈ `#fee2e2` ≈ `#f3e8ff` ≈ `#fff` ≈ `#e5e7eb` ≈ `#f9fafb` ≈ `#ffffff`
- `#1d4ed8` ≈ `#2563eb`
- `#166534` ≈ `#065f46`
- `#4b5563` ≈ `#374151`
- `#fef9c3` ≈ `#fef3c7` ≈ `#ffedd5`
- `#b45309` ≈ `#a16207` ≈ `#c2410c`
- `#854d0e` ≈ `#92400e`
- `#a5b4fc` ≈ `#93c5fd`
- `#9ca3af` ≈ `#94a3b8`

## 2. Proposed token set (Fortnox-grade restraint)

Defined as CSS variables in `globals.css` (the repo's existing pattern — the
`--vf-*` var system already exists and is theme-aware; we consolidate INTO it,
not around it).

### Colors — 1 accent + 4 semantics + 1 neutral ramp
| Token | Light | Dark | Role |
|---|---|---|---|
| `--vf-accent` | *(pending your pick — see options below)* | auto-derived | THE brand color: primary buttons, active nav, links, focus |
| `--vf-success` | `#16a34a` | `#4ade80` | paid / approved / positive |
| `--vf-warning` | `#d97706` | `#fbbf24` | overdue-soon / pending |
| `--vf-danger` | `#dc2626` | `#f87171` | overdue / rejected / destructive |
| `--vf-info` | `#0369a1` | `#38bdf8` | neutral notices |
| neutrals | Tailwind `slate` ramp only | inverted | text/borders/surfaces (drop gray/zinc/neutral/stone) |

**Accent options (you said you dislike the current indigo/blue):**
- **A. Nordic Green `#1f7a4d`** — Fortnox-adjacent; reads "Swedish accounting software"; calm, trustworthy (my recommendation)
- **B. Deep Teal `#0f766e`** — modern SaaS, distinct from every competitor
- **C. Muted Steel Blue `#2f5ea8`** — safest B2B choice, less "template-y" than the current `#2563eb`

### Spacing — 4px scale, Tailwind defaults only
Allowed steps: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64 px (`p-1…p-16`).
Rule: **no `[Npx]` arbitrary spacing.** (42 distinct arbitrary values today.)

### Radii — 2
| Token | Value | Use |
|---|---|---|
| `--vf-radius-sm` | 8px (`rounded-lg`) | inputs, buttons, chips, table cells |
| `--vf-radius-lg` | 12px (`rounded-xl`) | cards, panels, modals |
(`rounded-full` stays for avatars/pills.)

### Shadows — 3
| Token | Use |
|---|---|
| `--vf-shadow-sm` | resting cards |
| `--vf-shadow-md` | hover / dropdowns |
| `--vf-shadow-lg` | modals / drawers |

### Type scale — 7 sizes
11 (meta) · 12 (labels) · 13 (table body) · 14 (body/inputs) · 16 (section h) ·
20 (page h) · 24 (screen title). Weights: 400 / 500 / 600 only.

## 3. Enforcement (ships in Phase 1B)
`frontend/scripts/check-tokens.sh` — greps for new `-[#`, `text-[Npx]`,
`rounded-[`, `shadow-[`, `p-[Npx]`-class values outside `globals.css`/token
files; wired as a CI step. Never introduce a new hardcoded color/radius/shadow.

## Gate 1A status
- [x] Report covers all of `frontend/src` ({d['files_scanned']} files)
- [x] Proposed set (1 accent + 4 semantic + 1 neutral ramp, 4px spacing, 2 radii, 3 shadows, 7 type sizes) is dramatically smaller than the inventory (188 hex / 19 families / 44 arbitrary)
- [ ] **STOPPED — awaiting approval + accent color choice before Phase 1B**
