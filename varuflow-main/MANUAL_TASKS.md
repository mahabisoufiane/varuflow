# MANUAL_TASKS.md — Varuflow Pre-Launch Manual Tasks

Generated: 2026-05-02

---

## Marketing Stack Audit Results

| Feature | Router | Model | Tests | Frontend | Status |
|---------|--------|-------|-------|----------|--------|
| Trial system | `routers/trial.py`, `routers/trial_admin.py` | `models/organization.py` (trial_ends_at) | `tests/test_trial.py` | `(marketing)/trial/page.tsx` | Complete |
| Plan limits enforcement | — (enforced via service) | — | `tests/test_plan_limits.py` | — | `services/plan_limits.py` exists |
| PostHog analytics | — | — | — | `PostHogInit.tsx`, `lib/analytics.ts` | Frontend only |
| Upsell engine | `routers/upsells.py` | `models/upsell.py` | `tests/test_upsells.py` | — | Backend complete, no frontend page |
| Marketing site | — | — | — | 22 pages in `(marketing)/` | Complete |
| Blog CMS | — | — | — | `blog/page.tsx`, `blog/[slug]/`, category, tag | Frontend shell exists |
| Accounting partner program | `routers/accounting_partners.py` | `models/accounting_partners.py` | `tests/test_accounting_partners.py` | `(marketing)/partners/page.tsx` | Complete |
| Operator referrals | `routers/operator_referrals.py` | `models/operator_referrals.py` | `tests/test_operator_referrals.py` | — | Backend complete |
| NPS + health scoring | `routers/nps.py` | `models/nps.py` | `tests/test_nps.py`, `tests/test_subscription_health.py` | `NpsSurveyModal.tsx` | Complete |
| Onboarding email sequence | — (service only) | `models/trial_sequences.py` | `tests/test_email_sequences.py` | — | `services/trial_sequences.py` exists |

---

## Section 1: External Service Accounts

### Stripe (SaaS Billing + Customer Payments)
- **Purpose**: Subscription billing for Varuflow plans; payment links for wholesaler invoices
- **Sign-up**: https://dashboard.stripe.com/register
- **Tier**: Standard (no monthly fee, 1.4% + 0.25 SEK per EU card)
- **Env vars**: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRO_PRICE_ID`
- **Where to find keys**: Stripe Dashboard > Developers > API Keys
- **Webhook URLs**:
  - SaaS billing: `https://varuflow-production.up.railway.app/api/billing/webhook`
  - Invoice payments: `https://varuflow-production.up.railway.app/api/invoicing/stripe-webhook`
- **Testing checklist**:
  - [ ] 🔴 Create Stripe account with Swedish business entity
  - [ ] 🔴 Configure webhook endpoints (both)
  - [ ] 🔴 Create Products: Free, Pro, Enterprise in Stripe dashboard
  - [ ] 🔴 Set STRIPE_PRO_PRICE_ID to the Pro plan's price ID
  - [ ] 🟡 Enable Stripe Tax for EU VAT handling
  - [ ] 🟡 Configure Stripe Customer Portal for self-service plan changes
  - [ ] 🟡 Test subscription lifecycle: create, upgrade, downgrade, cancel
  - [ ] 🟡 Test webhook signature verification with test events
  - **Est. time**: 4 hours | **Cost**: Free to set up, transaction fees only

### Resend (Transactional Email)
- **Purpose**: Invoice emails, password resets, trial notifications, dunning emails
- **Sign-up**: https://resend.com/signup
- **Tier**: Pro ($20/month for 50k emails) — needed for custom domain sending
- **Env vars**: `RESEND_API_KEY`
- **Where to find keys**: Resend Dashboard > API Keys
- **Webhook URLs**: None required (delivery status via API polling)
- **Testing checklist**:
  - [ ] 🔴 Create account and verify sending domain (varuflow.se)
  - [ ] 🔴 Add DNS records (SPF, DKIM, DMARC) for varuflow.se
  - [ ] 🔴 Generate API key and set in Railway
  - [ ] 🟡 Test email delivery to Gmail, Outlook, and custom domains
  - [ ] 🟡 Set up bounce/complaint webhooks for list hygiene
  - **Est. time**: 2 hours | **Cost**: $20/month

### Sentry (Error Monitoring)
- **Purpose**: Backend exception tracking, performance monitoring
- **Sign-up**: https://sentry.io/signup/
- **Tier**: Team ($26/month for 50k events)
- **Env vars**: `SENTRY_DSN`
- **Where to find keys**: Sentry > Project Settings > Client Keys (DSN)
- **Webhook URLs**: None
- **Testing checklist**:
  - [ ] 🔴 Create organization and Python project
  - [ ] 🔴 Set SENTRY_DSN in Railway
  - [ ] 🟡 Configure alert rules (notify on first occurrence of new issue)
  - [ ] 🟡 Set up Slack/email integration for alerts
  - [ ] 🟢 Configure performance monitoring sample rate (0.1 for production)
  - **Est. time**: 1 hour | **Cost**: $26/month

### PostHog (Product Analytics)
- **Purpose**: User behavior tracking, feature flags, session replay
- **Sign-up**: https://posthog.com/signup
- **Tier**: Free up to 1M events/month; Scale at $0.00031/event after
- **Env vars**: `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`
- **Where to find keys**: PostHog > Project Settings > Project API Key
- **Webhook URLs**: None
- **Testing checklist**:
  - [ ] 🔴 Create project (EU Cloud instance for GDPR)
  - [ ] 🔴 Set env vars in Vercel
  - [ ] 🟡 Define key events: signup, trial_start, first_invoice, upgrade
  - [ ] 🟡 Create conversion funnels: Signup > Onboarding > First Invoice > Paid
  - [ ] 🟡 Set up feature flags for gradual rollouts
  - [ ] 🟢 Configure session replay (sample 10% of sessions)
  - **Est. time**: 3 hours | **Cost**: Free initially

### Sanity.io (Blog CMS)
- **Purpose**: Headless CMS for marketing blog content
- **Sign-up**: https://www.sanity.io/get-started
- **Tier**: Free (3 users, 500k API requests/month)
- **Env vars**: `NEXT_PUBLIC_SANITY_PROJECT_ID`, `NEXT_PUBLIC_SANITY_DATASET`, `SANITY_API_TOKEN`
- **Where to find keys**: Sanity > Manage > API > Tokens
- **Webhook URLs**: `https://varuflow.vercel.app/api/revalidate` (ISR webhook)
- **Testing checklist**:
  - [ ] 🟡 Create Sanity project with blog schema (post, author, category, tag)
  - [ ] 🟡 Set up Sanity Studio at studio.varuflow.se or /studio
  - [ ] 🟡 Configure GROQ queries in frontend blog pages
  - [ ] 🟡 Set up ISR revalidation webhook on publish
  - [ ] 🟢 Create initial 5 blog posts for SEO
  - **Est. time**: 8 hours | **Cost**: Free

### Supabase (Auth + Database)
- **Purpose**: User authentication (email/password, magic link), PostgreSQL hosting
- **Sign-up**: https://supabase.com/dashboard
- **Tier**: Pro ($25/month, 8GB DB, 250 concurrent connections)
- **Env vars**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Where to find keys**: Supabase Dashboard > Project Settings > API
- **Testing checklist**:
  - [ ] 🔴 Create project in EU region (Stockholm)
  - [ ] 🔴 Configure auth providers (email/password)
  - [ ] 🔴 Set JWT secret and service key in Railway + Vercel
  - [ ] 🔴 Run Alembic migrations against production DB
  - [ ] 🟡 Configure Row Level Security policies (if using Supabase direct access)
  - [ ] 🟡 Set up daily DB backups (Point-in-Time Recovery on Pro)
  - **Est. time**: 3 hours | **Cost**: $25/month

### Railway (Backend Hosting)
- **Purpose**: FastAPI backend hosting, environment variables
- **Sign-up**: https://railway.app/
- **Tier**: Pro ($20/month base + usage)
- **Env vars**: All backend vars listed in CLAUDE.md
- **Where to find keys**: Railway > Project > Variables
- **Testing checklist**:
  - [ ] 🔴 Create project, link GitHub repo
  - [ ] 🔴 Set all 25+ env vars from CLAUDE.md
  - [ ] 🔴 Configure custom domain (api.varuflow.se)
  - [ ] 🔴 Verify /api/health returns 200
  - [ ] 🟡 Set up auto-deploy from main branch
  - [ ] 🟡 Configure resource limits (2GB RAM, 2 vCPU)
  - **Est. time**: 2 hours | **Cost**: ~$20-50/month

### Vercel (Frontend Hosting)
- **Purpose**: Next.js frontend hosting, edge functions
- **Sign-up**: https://vercel.com/signup
- **Tier**: Pro ($20/month per member)
- **Env vars**: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_POSTHOG_KEY`
- **Where to find keys**: Vercel > Project > Settings > Environment Variables
- **Testing checklist**:
  - [ ] 🔴 Import project from GitHub
  - [ ] 🔴 Set all frontend env vars
  - [ ] 🔴 Configure custom domain (varuflow.se, www.varuflow.se)
  - [ ] 🔴 Verify build succeeds with `npm install --legacy-peer-deps`
  - [ ] 🟡 Configure preview deployments for PRs
  - **Est. time**: 1 hour | **Cost**: $20/month

### OpenAI (AI Features)
- **Purpose**: GPT-4o chat assistant for wholesalers
- **Sign-up**: https://platform.openai.com/signup
- **Tier**: Pay-as-you-go (GPT-4o: $2.50/1M input tokens, $10/1M output tokens)
- **Env vars**: `OPENAI_API_KEY`
- **Where to find keys**: OpenAI Platform > API Keys
- **Testing checklist**:
  - [ ] 🔴 Create organization and generate API key
  - [ ] 🔴 Set spending limit ($50/month initially)
  - [ ] 🟡 Monitor token usage via dashboard
  - [ ] 🟡 Set up usage alerts at 80% of limit
  - **Est. time**: 30 min | **Cost**: ~$20-100/month depending on usage

### Open Exchange Rates (FX)
- **Purpose**: Currency conversion for multi-country invoicing (SEK, NOK, DKK, EUR)
- **Sign-up**: https://openexchangerates.org/signup
- **Tier**: Developer ($12/month, 10k requests/month)
- **Env vars**: `OPEN_EXCHANGE_RATES_APP_ID`
- **Where to find keys**: Dashboard > App IDs
- **Testing checklist**:
  - [ ] 🟡 Create account and get App ID
  - [ ] 🟡 Verify SEK, NOK, DKK, EUR rates are available
  - [ ] 🟡 Implement caching (refresh rates every 4 hours max)
  - **Est. time**: 30 min | **Cost**: $12/month

---

## Section 2: DNS + Domain Configuration

### Primary Domain: varuflow.se

| Record Type | Host | Value | Purpose | Priority |
|-------------|------|-------|---------|----------|
| A | @ | 76.76.21.21 | Vercel (frontend) | 🔴 |
| CNAME | www | cname.vercel-dns.com | Vercel www redirect | 🔴 |
| CNAME | api | varuflow-production.up.railway.app | Railway backend | 🔴 |
| TXT | @ | v=spf1 include:resend.com ~all | SPF for email | 🔴 |
| TXT | resend._domainkey | (from Resend dashboard) | DKIM signing | 🔴 |
| TXT | _dmarc | v=DMARC1; p=quarantine; rua=mailto:dmarc@varuflow.se | DMARC policy | 🔴 |
| MX | @ | feedback-smtp.eu-west-1.amazonses.com | Inbound email (if needed) | 🟡 |
| CNAME | status | statuspage.betteruptime.com | Status page | 🟡 |
| TXT | @ | google-site-verification=... | Google Search Console | 🟡 |

### Subdomain Routing
- `varuflow.se` / `www.varuflow.se` → Vercel (marketing + app)
- `api.varuflow.se` → Railway (backend API)
- `status.varuflow.se` → BetterUptime status page
- `studio.varuflow.se` → Sanity Studio (optional, can be /studio path)

### SSL Certificates
- [ ] 🔴 Vercel auto-provisions SSL for frontend domains (no action needed)
- [ ] 🔴 Railway auto-provisions SSL for api.varuflow.se via Let's Encrypt
- [ ] 🔴 Verify HTTPS redirect is enforced (no HTTP access)
- **Est. time**: 2 hours | **Cost**: Domain ~$15/year (via Namecheap or GoDaddy)

---

## Section 3: Compliance + Legal Tasks

### Swedish Company Registration
- [ ] 🔴 Register AB (Aktiebolag) with Bolagsverket — https://bolagsverket.se/fo/foretag/aktiebolag/starta
  - Minimum share capital: 25,000 SEK
  - Required: company name, board of directors, articles of association
  - Timeline: 1-3 weeks
  - **Est. time**: 8 hours of paperwork | **Cost**: 25,000 SEK capital + 2,200 SEK registration fee

### VAT Registration
- [ ] 🔴 Register for F-skatt and Moms with Skatteverket — https://www.skatteverket.se/foretag/drivaforetag/startaforetag
  - Swedish VAT number (SE + org number + 01)
  - Required for B2B invoicing
  - Timeline: 2-4 weeks
  - **Est. time**: 2 hours | **Cost**: Free

### IMY (Integritetsskyddsmyndigheten) Registration
- [ ] 🔴 Register as data controller with IMY — https://www.imy.se/verksamhet/dataskydd/
  - Required under GDPR for processing personal data
  - Appoint a DPO (Data Protection Officer) or document why one is not needed
  - **Est. time**: 4 hours | **Cost**: Free

### GDPR Data Processing Agreements
- [ ] 🔴 Sign DPA with Supabase (available in their dashboard)
- [ ] 🔴 Sign DPA with Railway (contact support)
- [ ] 🔴 Sign DPA with Vercel (available at vercel.com/legal/dpa)
- [ ] 🔴 Sign DPA with OpenAI (available at openai.com/policies/data-processing-addendum)
- [ ] 🔴 Sign DPA with Stripe (available in Stripe dashboard)
- [ ] 🔴 Sign DPA with Resend (contact support)
- [ ] 🟡 Sign DPA with PostHog (EU hosting makes this simpler)
- **Est. time**: 4 hours total | **Cost**: Free (included in service agreements)

### Privacy Policy
- [ ] 🔴 Draft privacy policy covering:
  - Data collected (name, email, org number, invoice data)
  - Legal basis (contract performance for customers, legitimate interest for analytics)
  - Data retention periods
  - Sub-processors list
  - Data subject rights (access, deletion, portability)
  - Cross-border transfers (Supabase EU, but OpenAI US)
  - Cookie policy
- [ ] 🔴 Publish at varuflow.se/privacy (page exists in frontend)
- [ ] 🔴 Swedish translation at varuflow.se/sv/privacy
- **Est. time**: 8 hours (or hire lawyer: 5,000-15,000 SEK) | **Cost**: 0-15,000 SEK

### Terms of Service
- [ ] 🔴 Draft ToS covering:
  - Service description and SLA (99.9% uptime target)
  - Payment terms (monthly/annual billing, auto-renewal)
  - Acceptable use policy
  - Limitation of liability
  - Termination and data export
  - Governing law (Swedish law, Stockholm courts)
- [ ] 🔴 Publish at varuflow.se/terms (page exists)
- **Est. time**: 8 hours (or hire lawyer) | **Cost**: 0-15,000 SEK

### Trademark
- [ ] 🟡 Register "Varuflow" trademark with PRV (Patent- och registreringsverket) — https://www.prv.se/varumarke/
  - Classes: 9 (software), 35 (business management), 42 (SaaS)
  - Timeline: 6-9 months
  - **Est. time**: 3 hours to file | **Cost**: 5,700 SEK (3 classes online)

---

## Section 4: Payment + Banking Setup

### Business Bank Account
- [ ] 🔴 Open a business bank account (SEB, Nordea, or Swedbank recommended for B2B SaaS)
  - Required: company registration certificate, board resolution, ID for signatories
  - Timeline: 1-2 weeks
  - **Est. time**: 4 hours | **Cost**: 200-500 SEK/month

### Stripe Business Verification
- [ ] 🔴 Complete Stripe identity verification:
  - Company registration number (organisationsnummer)
  - Beneficial owner information
  - Bank account for payouts (IBAN)
  - Expected transaction volume estimate
  - **Est. time**: 2 hours | **Cost**: Free

### Payment Methods — Nordic Markets
- [ ] 🟡 Enable Stripe-native methods:
  - Credit/debit cards (Visa, Mastercard)
  - SEPA Direct Debit (for EU B2B)
  - Bancontact (Belgium, if expanding)
- [ ] 🟡 Klarna integration (popular in Sweden for B2B)
  - Sign up at https://www.klarna.com/se/foretag/
  - Invoice payment (Klarna faktura) — 30 day terms
  - **Est. time**: 4 hours | **Cost**: 2.49% + 3.29 SEK per transaction
- [ ] 🟢 Swish for Business (Sweden mobile payments)
  - Apply via your bank (SEB/Nordea)
  - Swish number tied to org number
  - **Est. time**: 2 hours | **Cost**: ~2 SEK per transaction
- [ ] 🟢 Vipps (Norway mobile payments)
  - Apply at https://portal.vipps.no/
  - Required for Norwegian market
  - **Est. time**: 2 hours | **Cost**: 1.75% per transaction

---

## Section 5: App Store Submissions

### Apple App Store (if PWA is insufficient)
- [ ] 🟢 Apple Developer Program — https://developer.apple.com/programs/
  - **Cost**: $99/year (899 SEK)
  - **Requirements**:
    - [ ] D-U-N-S Number for organization (free from Dun & Bradstreet)
    - [ ] App Store Connect account setup
    - [ ] App icons (1024x1024 PNG, no alpha)
    - [ ] Screenshots: 6.7" (1290x2796), 6.5" (1284x2778), 5.5" (1242x2208), iPad 12.9"
    - [ ] Privacy nutrition labels
    - [ ] App description (4000 chars), subtitle (30 chars), keywords (100 chars)
    - [ ] Review guidelines compliance (especially 4.2 minimum functionality)
    - [ ] Export compliance (HTTPS counts as encryption — select YES, then exempt)
  - **Timeline**: 1-7 days review
  - **Est. time**: 16 hours | **Cost**: $99/year

### Google Play Store
- [ ] 🟢 Google Play Developer account — https://play.google.com/console/
  - **Cost**: $25 one-time
  - **Requirements**:
    - [ ] Feature graphic (1024x500)
    - [ ] Screenshots: phone (min 2), 7" tablet, 10" tablet
    - [ ] Hi-res icon (512x512)
    - [ ] Short description (80 chars), full description (4000 chars)
    - [ ] Content rating questionnaire
    - [ ] Data safety form (declare all data collected)
    - [ ] Target audience declaration
    - [ ] Privacy policy URL (required)
  - **Timeline**: 2-7 days review
  - **Est. time**: 12 hours | **Cost**: $25

### Huawei AppGallery
- [ ] 🟢 Huawei Developer account — https://developer.huawei.com/consumer/en/appgallery
  - **Cost**: Free
  - **Requirements**:
    - [ ] Business verification documents
    - [ ] Screenshots (1080x1920 minimum)
    - [ ] App description in English + supported locales
    - [ ] Privacy policy URL
    - [ ] App signing certificate
  - **Timeline**: 3-5 days review
  - **Est. time**: 8 hours | **Cost**: Free

---

## Section 6: Marketing Asset Creation

### Logo + Brand Identity
- [ ] 🔴 Primary logo (SVG + PNG at 1x, 2x, 3x)
- [ ] 🔴 Favicon set (16x16, 32x32, 180x180 apple-touch-icon, 512x512 PWA icon)
- [ ] 🔴 Brand color palette (primary, secondary, accent, neutrals — for light/dark mode)
- [ ] 🔴 Typography selection (headings + body, must support Swedish characters: å, ä, ö)
- [ ] 🟡 Brand guidelines document (logo usage, spacing, colors, do/don't)
- [ ] 🟡 Social media profile images (LinkedIn: 400x400 + banner 1128x191)
- **Est. time**: 20 hours (or agency: 15,000-50,000 SEK) | **Cost**: 0-50,000 SEK

### Product Screenshots
- [ ] 🟡 Dashboard overview (desktop + mobile)
- [ ] 🟡 Invoice creation flow
- [ ] 🟡 Inventory management
- [ ] 🟡 AI assistant in action
- [ ] 🟡 Customer portal
- [ ] 🟡 Analytics dashboard
- [ ] 🟡 POS interface
- **Est. time**: 4 hours | **Cost**: Free (use real app with test data)

### Demo Video
- [ ] 🟡 Product walkthrough video (2-3 minutes)
  - Script covering: onboarding, creating invoice, inventory check, AI assistant
  - Professional voiceover (Swedish + English)
  - Screen recording with animations
- **Est. time**: 16 hours | **Cost**: 5,000-20,000 SEK (freelancer) or DIY with Loom

### Pitch Deck
- [ ] 🟡 Investor/partner pitch deck (12-15 slides):
  - Problem, solution, market size, product demo, business model, traction, team, ask
- **Est. time**: 8 hours | **Cost**: Free (Canva/Figma) or 5,000 SEK (designer)

---

## Section 7: Content Creation

### Founder / Team Bio
- [ ] 🟡 Professional headshot for each team member
- [ ] 🟡 Bio text (100 words each) for About page
- [ ] 🟡 LinkedIn profiles updated with Varuflow branding
- **Est. time**: 2 hours | **Cost**: 500-2,000 SEK (photographer)

### Legal Pages (already have frontend routes)
- [ ] 🔴 Privacy Policy — full GDPR-compliant text (see Section 3)
- [ ] 🔴 Terms of Service — full legal text (see Section 3)
- [ ] 🔴 Cookie Policy — categories: necessary, analytics, marketing
- [ ] 🟡 Acceptable Use Policy
- [ ] 🟡 SLA document (99.9% uptime guarantee)
- **Est. time**: 16 hours total | **Cost**: 10,000-30,000 SEK (lawyer)

### Blog Articles (for SEO + thought leadership)
- [ ] 🟡 "Digitalisering av grossisthandeln i Sverige" (pillar page, 2000+ words)
- [ ] 🟡 "Så väljer du rätt affärssystem för grossist" (comparison guide)
- [ ] 🟡 "Automatisk fakturering — spara 10 timmar per vecka"
- [ ] 🟡 "Guide: E-faktura och Peppol för B2B-företag"
- [ ] 🟡 "Lagerhantering i realtid — varför det spelar roll"
- [ ] 🟢 "AI i grossistbranschen — framtidens möjligheter"
- [ ] 🟢 "Fortnox-integration: Så kopplar du ditt bokföringssystem"
- [ ] 🟢 "Kundportal för grossister — öka kundnöjdheten"
- [ ] 🟢 "Kassasystem för grossist — allt du behöver veta"
- [ ] 🟢 "Prisstrategier för nordiska grossister"
- **Est. time**: 40 hours (10 articles x 4h each) | **Cost**: Free (DIY) or 3,000 SEK/article

### LinkedIn Content Strategy
- [ ] 🟡 Company page created and branded
- [ ] 🟡 Content calendar (2 posts/week minimum)
- [ ] 🟡 Post templates: product updates, industry insights, customer stories
- **Est. time**: 4 hours setup | **Cost**: Free

---

## Section 8: SEO + Analytics Setup

### Google Search Console
- [ ] 🔴 Verify domain ownership (DNS TXT record)
- [ ] 🔴 Submit sitemap (varuflow.se/sitemap.xml — Next.js generates automatically)
- [ ] 🟡 Configure URL parameters
- [ ] 🟡 Monitor Core Web Vitals
- **URL**: https://search.google.com/search-console/
- **Est. time**: 1 hour | **Cost**: Free

### Google Analytics 4 (optional, PostHog may suffice)
- [ ] 🟢 Create GA4 property
- [ ] 🟢 Configure conversion events: sign_up, start_trial, purchase
- [ ] 🟢 Link to Google Search Console
- [ ] 🟢 Set up Google Ads conversion tracking (if running ads)
- **Est. time**: 2 hours | **Cost**: Free

### PostHog Dashboards
- [ ] 🟡 Signup funnel: Landing > Trial signup > Onboarding complete > First invoice > Paid
- [ ] 🟡 Feature adoption: % of users using AI, POS, recurring invoices, portal
- [ ] 🟡 Retention cohorts: weekly/monthly active users
- [ ] 🟡 Revenue metrics: MRR, churn, expansion (via Stripe integration)
- **Est. time**: 4 hours | **Cost**: Free (included in PostHog)

### Technical SEO
- [ ] 🔴 Verify sitemap.xml is generated and accessible
- [ ] 🔴 robots.txt allows crawling of marketing pages, blocks /portal/ and app routes
- [ ] 🟡 Structured data (JSON-LD): Organization, Product, FAQ on relevant pages
- [ ] 🟡 Open Graph meta tags on all marketing pages
- [ ] 🟡 Hreflang tags for sv/en/no/da alternate pages
- [ ] 🟡 Canonical URLs set correctly
- **Est. time**: 6 hours | **Cost**: Free

---

## Section 9: Sales + Outreach Setup

### LinkedIn Sales Navigator
- [ ] 🟡 Subscribe to Sales Navigator Professional — https://business.linkedin.com/sales-solutions
  - Filter: Industry = Wholesale, Location = Sweden/Norway/Denmark, Company size = 10-500
  - **Est. time**: 2 hours | **Cost**: ~900 SEK/month

### Prospect List Building
- [ ] 🟡 Identify top 100 Nordic wholesalers by segment:
  - Food & beverage distributors
  - Building materials wholesalers
  - Electronics/IT distributors
  - Fashion/textile wholesalers
  - Industrial supplies
- [ ] 🟡 Enrich with decision-maker contacts (CFO, COO, IT Manager)
- [ ] 🟡 Verify emails via Hunter.io or Clearbit
- **Est. time**: 16 hours | **Cost**: 500-2,000 SEK (email verification tools)

### Email Outreach Sequences
- [ ] 🟡 Cold outreach sequence (4 emails over 14 days):
  1. Introduction + pain point (manual invoicing costs)
  2. Case study / social proof
  3. Feature highlight (AI assistant, Fortnox integration)
  4. Final follow-up + demo offer
- [ ] 🟡 Set up outreach tool (Lemlist, Instantly, or Apollo)
- [ ] 🟡 Warm leads sequence (from website demo requests)
- **Est. time**: 8 hours | **Cost**: $50-100/month (outreach tool)

### Demo Environment
- [ ] 🟡 Create demo organization with realistic Swedish wholesaler data:
  - 50+ products with SKUs
  - 20+ customers with realistic Swedish company names
  - Sample invoices, recurring schedules
  - AI action cards pre-populated
- **Est. time**: 4 hours | **Cost**: Free

---

## Section 10: Customer Success Setup

### Help Center / Knowledge Base
- [ ] 🟡 Choose platform: Intercom, Crisp, or self-hosted (Docusaurus)
- [ ] 🟡 Write help articles for core flows:
  - Getting started / onboarding
  - Creating your first invoice
  - Setting up recurring invoices
  - Connecting Fortnox
  - Inviting team members
  - Using the customer portal
  - AI assistant guide
  - POS setup
- [ ] 🟡 Create video walkthroughs for each (Loom or similar)
- **Est. time**: 24 hours | **Cost**: Free-$50/month (tool)

### Onboarding Content
- [ ] 🟡 In-app onboarding checklist (already partially in `models/onboarding.py`):
  - Add first product
  - Create first customer
  - Send first invoice
  - Connect accounting (Fortnox)
  - Invite team member
- [ ] 🟡 Welcome email sequence (automated via trial_sequences.py):
  - Day 0: Welcome + quickstart guide
  - Day 1: Feature spotlight (invoicing)
  - Day 3: Feature spotlight (AI assistant)
  - Day 7: Check-in + offer help
  - Day 12: Trial ending reminder + upgrade CTA
- **Est. time**: 8 hours | **Cost**: Free

### Status Page
- [ ] 🔴 Set up BetterUptime or Instatus — https://betteruptime.com/
  - Monitor: /api/health endpoint
  - Configure: status.varuflow.se subdomain
  - Incident communication templates
- **Est. time**: 1 hour | **Cost**: Free tier available

### Community
- [ ] 🟢 Create LinkedIn group for Nordic wholesalers
- [ ] 🟢 Consider Discord/Slack community for power users
- **Est. time**: 2 hours | **Cost**: Free

---

## Section 11: Operations + Infrastructure

### Database Backups
- [ ] 🔴 Supabase Pro includes Point-in-Time Recovery (verify enabled)
- [ ] 🔴 Configure daily logical backups (pg_dump) to external storage
  - Destination: S3-compatible bucket (Backblaze B2 or AWS S3)
  - Retention: 30 daily, 12 weekly, 6 monthly
- [ ] 🟡 Test backup restoration procedure (document in runbook)
- [ ] 🟡 Set up backup monitoring alerts (alert if backup is >24h old)
- **Est. time**: 4 hours | **Cost**: $5-20/month (storage)

### Monitoring + Alerting
- [ ] 🔴 Sentry for error tracking (see Section 1)
- [ ] 🔴 UptimeRobot or BetterUptime for availability monitoring
  - Checks: /api/health every 60 seconds
  - Alert channels: SMS + email + Slack
- [ ] 🟡 Resource monitoring on Railway (CPU, memory, disk)
- [ ] 🟡 Database connection pool monitoring
- [ ] 🟡 Set up PagerDuty or Opsgenie for on-call rotation (when team grows)
- **Est. time**: 4 hours | **Cost**: Free-$30/month

### Incident Response Plan
- [ ] 🟡 Document incident severity levels:
  - P1: Complete outage (all customers affected) — respond in 15 min
  - P2: Major feature broken (invoicing, auth) — respond in 1 hour
  - P3: Minor feature degraded — respond in 4 hours
  - P4: Cosmetic/non-urgent — next business day
- [ ] 🟡 Create incident response runbook:
  - How to access Railway logs
  - How to rollback a deployment
  - How to failover database
  - Communication templates for status page
- **Est. time**: 4 hours | **Cost**: Free

### GDPR Operational Tools
- [ ] 🔴 Implement data export endpoint (GDPR Article 20 — data portability)
  - Already have `/api/gdpr/` router — verify it exports all user data as JSON
- [ ] 🔴 Implement data deletion endpoint (GDPR Article 17 — right to erasure)
  - Soft-delete user data, hard-delete after 30-day grace period
- [ ] 🟡 Data retention automation:
  - Delete inactive trial accounts after 90 days
  - Purge audit logs after 2 years
  - Anonymize analytics data after 26 months
- [ ] 🟡 Cookie consent banner (Cookiebot or custom)
  - Must block PostHog/analytics until consent given
- **Est. time**: 8 hours | **Cost**: Free-$10/month (Cookiebot)

### Security Operations
- [ ] 🔴 Enable 2FA for all admin accounts (Railway, Vercel, Supabase, Stripe, GitHub)
- [ ] 🔴 Rotate all API keys and secrets quarterly (document rotation procedure)
- [ ] 🟡 Set up Dependabot or Snyk for dependency vulnerability scanning
- [ ] 🟡 Annual penetration test (or use automated tools: OWASP ZAP, Burp Suite)
- [ ] 🟡 SOC 2 Type I preparation (if targeting enterprise customers)
- **Est. time**: 8 hours initial + ongoing | **Cost**: 10,000-50,000 SEK (pentest)

---

## Section 12: Financial Setup

### Accounting Software
- [ ] 🔴 Set up Fortnox for Varuflow's own accounting — https://www.fortnox.se/
  - Use Varuflow's own Fortnox integration (dog-fooding)
  - Configure: chart of accounts, VAT codes, fiscal year
  - **Est. time**: 4 hours | **Cost**: 299-699 SEK/month

### Tax Filing
- [ ] 🔴 Register for momsredovisning (VAT reporting) — monthly or quarterly
  - File via Skatteverket e-tjänster
  - Deadline: 12th of second month after reporting period
- [ ] 🔴 Employer registration (arbetsgivarregistrering) if hiring
  - Monthly employer contributions (arbetsgivaravgifter): 31.42%
- [ ] 🟡 Corporate tax preparation (bolagsskatt): 20.6%
  - Annual filing with Bolagsverket (årsredovisning)
  - Deadline: 7 months after fiscal year end
- **Est. time**: 4 hours setup + ongoing | **Cost**: 2,000-5,000 SEK/month (accountant)

### Financial Projections
- [ ] 🟡 Build financial model covering:
  - Revenue: MRR growth (pricing tiers x customer count)
  - Costs: Infrastructure ($150-300/month), SaaS tools ($200/month), salaries
  - Unit economics: CAC, LTV, LTV/CAC ratio
  - Cash runway calculation
  - Break-even analysis
- [ ] 🟡 Monthly P&L tracking (automate via Fortnox)
- **Est. time**: 8 hours | **Cost**: Free (spreadsheet) or 5,000 SEK (financial advisor)

### Pricing Strategy Validation
- [ ] 🟡 Confirm pricing tiers are competitive:
  - Free: up to 5 invoices/month, 1 user (lead gen)
  - Pro: 499 SEK/month — unlimited invoices, 5 users, AI, integrations
  - Enterprise: 1,499 SEK/month — unlimited everything, API access, SLA, dedicated support
- [ ] 🟡 Research competitor pricing (Fortnox, Visma, Wint, Zervant)
- [ ] 🟡 Calculate break-even: ~40 Pro customers or ~15 Enterprise customers
- **Est. time**: 4 hours | **Cost**: Free

---

## Summary: Cost Estimates

| Category | Monthly Cost | One-time Cost |
|----------|-------------|---------------|
| Hosting (Railway + Vercel + Supabase) | ~$65/month | — |
| SaaS tools (Resend, Sentry, PostHog, OpenAI) | ~$80-180/month | — |
| Domain + DNS | ~$1.25/month | $15/year |
| Company registration | — | 27,200 SEK |
| Legal (Privacy Policy, ToS, Trademark) | — | 25,000-80,000 SEK |
| Marketing assets (logo, video, photos) | — | 20,000-70,000 SEK |
| Accounting software | 299-699 SEK/month | — |
| Payment processing fees | Variable (1.4-2.5%) | — |
| **Total estimated monthly burn** | **~3,000-5,000 SEK/month** | — |
| **Total estimated one-time setup** | — | **~75,000-180,000 SEK** |

---

## Priority Timeline

### Week 1 (🔴 Critical — blocks launch)
- Company registration + bank account
- All external service accounts created
- DNS configured
- CORS, auth, health check verified in production
- Privacy Policy + ToS drafted

### Weeks 2-4 (🟡 High priority)
- Blog CMS connected (Sanity)
- PostHog dashboards built
- Onboarding email sequence activated
- Help center articles written
- Demo environment with test data
- SEO technical setup
- LinkedIn company page + first posts

### Months 2-3 (🟢 Medium priority)
- App store submissions (if needed)
- Community building
- Additional payment methods (Klarna, Swish, Vipps)
- Penetration test
- Content marketing cadence (2 blog posts/week)
- Partner program outreach to accounting firms
