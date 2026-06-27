# Design Sync Notes — Varuflow UI

## Setup quirks

- **Node**: Not in PATH by default (NVM-only). Always use full path `/home/smahabi/.nvm/versions/node/v22.22.2/bin/node` or set `PATH=/home/smahabi/.nvm/versions/node/v22.22.2/bin:$PATH` before running any node/npm command.
- **Package manager**: npm (package-lock.json in `frontend/`).
- **Converter working dir**: Run from repo root (`varuflow-main/`).
- **Non-existent entry anchor**: Pass `--entry frontend/src/components/_ds_anchor_nonexistent` to set `PKG_DIR=frontend/` without providing a real entry — this keeps synth-entry mode active (esbuild synthesizes from all src files). Do NOT create this file.
- **CSS**: Pre-compile Tailwind before converter runs: `cd frontend && node_modules/.bin/tailwindcss -i src/app/globals.css -o ds-styles.css --content 'src/**/*.tsx,src/**/*.ts'` (node must be in PATH). Output: `frontend/ds-styles.css`. Source CSS is `src/app/globals.css` (plain CSS, not SCSS).

## Excluded components (cfg.componentSrcMap null)

- **DataTable** (`ui/DataTable.tsx`) — imports `DataTable.module.scss` which esbuild cannot process. Heavily relies on SCSS module class names for layout. To re-include: refactor to Tailwind utilities.
- **Section** (`ui/Section.tsx`) — imports `Section.module.scss`. Same issue.
- **SectionBody, SectionFooter, SectionHeader** — sub-exports from `Section.tsx`; excluded because Section.tsx itself is excluded. ts-morph discovers them anyway (it reads all tsx files) so they must be explicitly nulled in componentSrcMap.
- **AppShell** (`app/AppShell.tsx`) — imports `AppShell.module.scss` + Supabase client + `@/i18n/navigation` + `next-intl`. Too many runtime-only dependencies to bundle statically.

## Re-sync risks

- `ds-styles.css` must be rebuilt whenever Tailwind classes or CSS tokens change. It is gitignored — rebuild before each sync.
- The non-existent entry anchor path must NOT be created (would switch esbuild to non-synth mode).
- Components using `next/link`, `next/navigation`, framer-motion etc. are bundled fine (those packages are in `frontend/node_modules`); only SCSS modules are the blocker.
- `cfg.provider` may be needed if previews fail with "usePathname: No router context" errors — check after first validate run.

---

## Preview authoring patterns (from 6-batch fan-out)

### When to use static replicas (do NOT import from `varuflow-ui`)

Write a pure plain-JSX replica (no import) whenever the component has any of these:

1. **`useTranslations()` / `useLocale()`** (next-intl) — throws without `<NextIntlClientProvider>`. Affects: AiCardCarousel, BankIDButton, CookieConsent, MobileBottomNav, MobileQuickActions, OnboardingChecklist, RecentActivity, AutoReorderBadge, LabelPrinter, LoyaltyCard, PosCartPanel, PosProductGrid, PosQuickButtons, PosReceiptModal, PosSessionControls.
2. **`useRouter()` / `useParams()` / `Link` from `@/i18n/navigation`** (next/navigation) — requires Next.js App Router context. Affects: CTABanner, HeroSection, PlanGate (locked overlay), TrialSignupForm, UpgradePromptInline, UpsellBanner, UpsellModal, LimitBlockedModal.
3. **`usePos()` context** — reads from PosProvider, makes API calls. Affects all POS components.
4. **API-driven state** — renders null/empty until fetch resolves. Affects: AiActionCards, WorkspaceSwitcher, CountryPicker.
5. **Event/state-driven visibility** — component hidden until a user event fires. Affects: CommandPalette (keyboard shortcut), CookieConsent (localStorage gate), MaintenanceBanner (CustomEvent), PwaInstallBanner (beforeinstallprompt), SessionTimeoutModal (Supabase session).
6. **`md:hidden` / `hidden lg:flex`** — invisible at desktop preview widths. Affects: MobileBottomNav, MobileQuickActions, AiChat.
7. **framer-motion / GSAP `animate from opacity:0`** — content invisible before IntersectionObserver fires in static capture. Affects: Reveal, ScrollReveal, Stagger.
8. **WASM / camera APIs** — react-zxing, getUserMedia. Affects: BarcodeInput, BarcodeScanner.

### Components that import cleanly (no context needed)

These imported from `varuflow-ui` successfully: Input, Label, Textarea, FormField, FormSection, MobileFormActions, Select (family), VFField, VFInput, VFLabel, VFOptional, VFSelect, VFTextarea, Card (family), Dialog (open prop), Skeleton, ThemeToggle (with ThemeProvider wrapper), Table (family), EmptyState (family), PageSkeleton, ScannerViewfinder, LimitWarningBanner, LockedFeatureCard, StaggerItem, ComparisonTable, ExitIntentModal, FeatureCard, LeadMagnetForm, LogoCloud, NewsletterSignup, NpsSurveyModal, PartnerApplicationForm, PlanGateBlock, StatBar, TestimonialCarousel.

### Special cases

- **Dialog**: Force `open={true}` prop — never use a Trigger in previews (closed state shows nothing).
- **ThemeToggle**: Wrap in `<ThemeProvider defaultTheme="...">` — has `mounted` guard that returns empty div before hydration.
- **Select family (Radix)**: Portal renders dropdown via Portal; screenshots show trigger in closed state — this is correct and expected.
- **EmptyState**: Inline SVG illustrations (don't import from `@/components/illustrations`). Use unique gradient IDs per SVG instance (suffix with index number to avoid conflicts).
- **SVG gradient ID conflicts**: When multiple SVGs with the same `<linearGradient id>` appear on one page, later ones shadow earlier ones. Always append a unique suffix.
- **Headless components** (no DOM output — floor cards only): PostHogInit, SentryInit, CrispChat, JsonLd, ThemeProvider (top-level), Toaster (next-themes dependency), RoleProvider, RoleGuard (API-gated).
- **UpsellToast**: Returns null; renders via Sonner toast side-effect. Static replica shows the toast card that would appear.

### Component API surprises

- **FormField**: Uses `kind` discriminant (not `type`). `onChange` delivers parsed value, not raw event. `kind="select"` takes `options: {value, label, disabled?}[]` array, not `<option>` children.
- **VFField**: Does not accept `required` prop — required asterisks live at FormField level. `optional?: boolean` shows the VFOptional badge.
- **VFInput/VFTextarea/VFSelect**: Use literal Tailwind classes (not CSS custom properties) — do not respond to dark-mode CSS vars like the `Input` component does.
- **MobileFormActions**: Uses `fixed inset-x-0 bottom-0` — floats in viewport. Wrap in `position: relative` container to contain it in preview.
- **TableRow**: Supports `data-[state=selected]` for row highlight — works in static HTML via `data-state="selected"` attribute.
- **TableCaption**: Always renders below table (`caption-bottom` CSS) regardless of JSX order.

### Emoji rendering in static captures

Emoji (📄 📦 👤 etc.) render as empty rectangle placeholders (□) in the capture screenshots. This is a headless Chrome font limitation — not a component bug. Structures using emoji as icons look blank but are otherwise complete. Grade as `good` if structure is correct.
