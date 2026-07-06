# Landing / Marketing Site — "Everything on it must work" plan

Audited 2026-07-06. Baseline: all 15 marketing routes render 200 (about, blog,
compliance-overview, contact, demo, features, partners, press, pricing,
security, trial, vs/fortnox, vs/visma, vs/bokio, vs/odoo). The gaps below are
what separates "renders" from "works".

## P0 — visitor actions that are broken or dead-end
1. **Newsletter + lead-magnet forms are broken** — both POST to
   `/api/waitlist/signup`, which returns **405 Method Not Allowed**. Every
   email captured on the landing page is silently lost. Find the real
   endpoint shape (or fix the backend route) and add success/error feedback.
   `components/marketing/{NewsletterSignup,LeadMagnetForm}.tsx` · S
2. **/demo has no form and no booking action** (zero form/fetch matches) —
   a "book a demo" page that can't book is a dead-end for the highest-intent
   visitors. Wire it to the Calendly links already in backend config
   (CALENDLY_* settings) or a simple contact-capture. · S/M
3. **Signup plan handoff unverified** — pricing CTAs link to
   `/auth/signup?plan=professional`; confirm signup actually reads `plan` and
   carries it through onboarding/billing. If it's dropped, pricing's main CTA
   half-works. · S (verify) + ? (fix)

## P1 — trust & market fit (Sweden-first)
4. **The Swedish site speaks English.** Hero, CTAs ("Start free trial"),
   sections — hardcoded EN strings served on `/sv`. For a Fortnox-competing
   Swedish product this undercuts trust on the first screen. Move landing copy
   to `messages/{sv,en}.json` (marketing namespace), write proper Swedish. · M
5. **Comparison pages content review** (`/vs/fortnox|visma|bokio|odoo`) —
   they render, but competitive claims must be accurate and current (pricing,
   feature checkmarks); wrong claims are a legal/credibility risk in SE.
   Needs your review of the claims; I verify structure/links. · M (human+me)
6. **Old-brand colors on the marketing site** — the (app) navy/blue sweep
   deliberately excluded (marketing); stale `#2563EB`/`#7c3aed` gradients and
   old-blue accents remain (HeaderNav fixed already; hero/sections not).
   Sweep marketing components onto the Steel Blue tokens. · S/M

## P2 — polish that sells
7. **Hero "app preview" is a fake mockup** — hand-drawn fake sidebar/content.
   Update it to mirror the real console (tree + Steel Blue + dense tables) or
   replace with a real screenshot. First thing every visitor inspects. · M
8. **Trial page ↔ signup flow coherence** — /trial renders; verify its CTA
   path and copy match the actual 14-day trial mechanics in backend
   (trial_* fields exist and are wired). · S
9. **Footer/legal completeness** — terms, privacy, security render; confirm
   press/partners content isn't placeholder lorem. · S (review)
10. **Blog** — works via Sanity seed fallback; decide: keep seeds, hide the
    nav link, or configure Sanity. · decision
11. **Mobile pass** — hamburger nav, hero scaling, comparison-table overflow
    on small screens. · S/M
12. **SEO/meta** — JsonLd component exists; verify per-page titles/descriptions
    + OG images on the 15 routes; sitemap. · M

## Verification gate (definition of "everything works")
- Every link on /, header, footer → 200 (currently true, keep true)
- Every form submits → visible success + row lands in DB (waitlist, partner,
  contact) — add these to the mutation smoke test
- Every CTA path ends somewhere real: signup (with plan), login, demo booking
- /sv is Swedish, /en is English, both themes
- tsc + token ratchet + build green
