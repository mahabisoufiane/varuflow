# Varuflow — Product Demo Video Script

**Target audience:** Nordic wholesale business owners (Swedish primary)  
**Tone:** Professional, fast-paced, show don't tell  
**Length:** ~3 minutes  
**Demo account:** demo@varuflow.se / Demo1234!

---

## Setup before recording

1. Run `python scripts/seed_demo.py` to populate the demo org
2. Sign in as `demo@varuflow.se`
3. Set browser to Swedish locale (`/sv/`)
4. Use a 1920×1080 window, hide bookmarks bar
5. Record at 2× speed, slow down to 1× for key moments

---

## Scene 1 — Dashboard (0:00 – 0:28)

**Screen:** `/sv/dashboard`

**What to show:**
- KPI row: "Fakturerat denna månad: 148 200 kr" / "Utestående: 86 500 kr" / "Förfallna: 3"
- Scroll to AI-cards: one "Stockout Risk" card for Skärmvägg (2 kvar, säljs 1.4/dag) → click "Skapa inköpsorder" button
- Watch the purchase order auto-create (toast notification appears)

**Voiceover / caption:**
> "Se hela din verksamhet på en sekund. Varuflow varnar dig innan du tar slut på varor — och skapar inköpsordern åt dig med ett klick."

---

## Scene 2 — Creating an Invoice (0:28 – 1:15)

**Screen:** `/sv/invoices` → New Invoice

**Steps:**
1. Click "Ny faktura"
2. Type "Berg" in customer field → autocomplete selects "Bergström & Partners AB"
3. Add line item: type "USB" → autocomplete selects "USB-C Dockningstation 12-port" → qty 5
4. Add second line: "Tang" → "Tangentbord Trådlöst SE" → qty 5
5. Watch totals auto-calculate: 14 195 kr inkl. moms
6. Click "Spara & Skicka" → invoice sent, toast appears
7. Switch to the invoice — show the green "Skickat" badge
8. Click "Betallänk" — Stripe payment link generates in 2 seconds

**Voiceover / caption:**
> "Skapa, skicka och få betalt — allt utan att lämna Varuflow. Kunden får en e-post med direkt betallänk via Stripe."

---

## Scene 3 — Inventory at a Glance (1:15 – 1:45)

**Screen:** `/sv/inventory`

**Steps:**
1. Show product list — 25 items, categories visible
2. Filter by "Kontorsmöbler"
3. Click on "Skärmvägg Tyg" — show detail: stock 2, min 4, red warning badge
4. Click on "Skrivbord Ek 140×70" — show: sell 4 990 kr, cost 2 100 kr, margin 58%
5. Switch to "Lagersaldon" tab — show per-warehouse stock grid

**Voiceover / caption:**
> "Fullständig lagerkontroll. Se marginaler, lagernivåer per lagerlokal och stockout-varningar i realtid."

---

## Scene 4 — Analytics (1:45 – 2:10)

**Screen:** `/sv/analytics`

**Steps:**
1. Show the revenue area chart — visible month-over-month growth (Jan → Jun)
2. Hover over May bar: 276 000 kr
3. Scroll to "Topp 5 kunder" bar chart — Norrköpings Kommun at top
4. Scroll to "Topp 5 produkter" — USB-C Dock leading
5. Click "Exportera PDF" — analytics report downloads

**Voiceover / caption:**
> "Analysera 6 månaders tillväxt i ett klick. Exportera rapporten som PDF till din revisor eller styrelse."

---

## Scene 5 — AI Assistant (2:10 – 2:38)

**Screen:** Any page — open floating AI chat (bottom right)

**Steps:**
1. Click the AI chat bubble
2. Type: "Vilka produkter har vi sålt mest av den senaste månaden?"
3. AI responds with ranked list and revenue figures
4. Type: "Föreslå ett pristest för USB-C dockan"
5. AI gives a concrete suggestion (increase price 10%, estimated impact +X kr/mån)

**Voiceover / caption:**
> "En inbyggd affärsrådgivare som känner din data. Ställ frågor på svenska — få svar på sekunder."

---

## Scene 6 — Customer Portal (2:38 – 3:00)

**Screen:** `/sv/customers` → Bergström & Partners

**Steps:**
1. Open customer detail
2. Click "Skicka portalinbjudan" — magic link sent (toast appears)
3. Open a new incognito window → paste the portal link
4. Show the portal: customer's own invoice list, PDF download button, "Betala nu" Stripe button
5. Zoom in on the "Betala nu" button

**Voiceover / caption:**
> "Kundportalen — kunden loggar in utan lösenord, ser sina fakturor och betalar direkt. Inga fler påminnelser i onödan."

---

## Outro (3:00 – 3:10)

**Screen:** Landing page hero or pricing page

**Text overlay:**
> Varuflow — Allt din grossistverksamhet behöver. Kom igång gratis på varuflow.se

---

## B-roll shots (record separately, use for transitions)

| Shot | Duration |
|------|----------|
| Dashboard loading (skeleton → data) | 2 s |
| Invoice PDF opening in browser | 2 s |
| Barcode scanner in POS view | 3 s |
| AI card animation expanding | 2 s |
| Mobile app (Expo) showing dashboard | 3 s |
| Settings → Fortnox connection going green | 2 s |

---

## Recording checklist

- [ ] Seed demo data: `cd backend && python scripts/seed_demo.py`
- [ ] Sign in as demo@varuflow.se
- [ ] Set locale to `/sv/`
- [ ] Hide all browser UI except the address bar
- [ ] Turn off notifications (macOS: Do Not Disturb / Windows: Focus Assist)
- [ ] Record audio separately (voiceover after video) for cleaner takes
- [ ] Use OBS or Loom — 1080p minimum, 60fps preferred
- [ ] Target ~3 min final cut; trim pauses aggressively

---

## Key numbers to highlight (pull from demo data)

| Metric | Value |
|--------|-------|
| Products in catalogue | 25 |
| Customers | 10 |
| Invoices sent last 6 months | ~60 |
| Revenue last month | ~276 000 kr |
| Revenue growth (5 months) | +119% |
| Outstanding balance | ~86 500 kr |
| Low-stock alerts | 3 products |
| AI insight cards | 5+ |
