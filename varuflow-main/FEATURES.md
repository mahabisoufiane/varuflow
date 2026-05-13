# Varuflow — Full Feature List

B2B SaaS platform for Nordic wholesalers (Sweden / Norway / Denmark).
Stack: Next.js 16 + FastAPI + PostgreSQL + Supabase Auth.

---

## 1. Core Commerce

| Feature | Description |
|---|---|
| Inventory Management | Products, variants, stock levels, reorder points, low-stock alerts |
| Purchase Orders | Create, send, and track supplier POs; line-item tracking |
| Point of Sale (POS) | In-store sales, receipt generation, shift management |
| Invoicing | Create, send, and track invoices; line items, taxes, discounts |
| Recurring Invoices | Schedule and auto-generate repeating invoices |
| Customer Management | Full customer profiles, contact details, purchase history |
| Quote Comparison | Side-by-side comparison of supplier quotes |
| Negotiated Pricing | Per-customer agreed prices stored and applied automatically |

---

## 2. Payments

| Feature | Description |
|---|---|
| Stripe Invoice Payments | Payment links on customer invoices |
| Apple Pay / Google Pay | Wallet-based checkout for customers |
| Saved Payment Methods | Customers save cards/wallets for one-click reuse |
| Stripe SaaS Billing | Subscription plans for Varuflow itself; grace period on failed payments |
| Wallet Pass (Apple / Google Wallet) | Loyalty cards and receipts pushed to native wallet apps |

---

## 3. Customer Portal

| Feature | Description |
|---|---|
| Branded Customer Portal | Token-gated portal at `/portal/{token}` — no login required |
| Invoice View & Pay | Customers view and pay invoices from the portal |
| Booking History | Full service/booking history visible to the customer |
| Service Status Tracking | Amazon-style live progress: stages, timestamps, staff photos |
| Live Tracking Session | Real-time job tracking with geo updates and photo proof |
| Digital Receipt | Receipt auto-categorized and available for download |
| Invoice Forwarding | Customer can forward invoice directly to their accountant |
| Calendar Sync | Customers sync bookings to Google / Apple / Outlook Calendar |
| Address Book | Customers manage multiple delivery/billing addresses |

---

## 4. B2B Buyer Features

| Feature | Description |
|---|---|
| Buyer Purchase Orders | Business customers create structured POs against the merchant |
| Approval Workflow | Multi-level PO approval with org member roles |
| Org Member Management | Buyer-side team members with spend limits and permissions |
| One-Click Reorder | Reorder a previous PO with a single action |
| Quote Comparison | Buyers compare multiple quotes side by side |

---

## 5. Booking & Scheduling

| Feature | Description |
|---|---|
| Booking Slots Config | Define provider capacity by day/time/service |
| Real-Time Capacity | Live slot availability surfaced to customers before booking |
| Return Pickup Scheduling | Book a pickup for returns; tracked through completion |
| Booking Insurance | Optional damage/liability insurance add-on at booking |
| Calendar Sync (Merchant) | Merchant bookings sync bidirectionally with Google / Outlook / Apple |

---

## 6. Customer Loyalty & Retention

| Feature | Description |
|---|---|
| Tiered Memberships | Bronze / Silver / Gold / Platinum tiers with benefits |
| Achievements | Unlock badges for milestones (first booking, 10th order, etc.) |
| Birthday Vouchers | Auto-generate and send discount vouchers on customer birthdays |
| Referral Tracking | Track referral sources, reward referrers, measure conversion |
| Loyalty Streaks | Reward consistent customers for consecutive activity periods |
| Personalized Recommendations | AI-driven product/service recommendations per customer |
| Important Dates | Staff-visible notes on customer anniversaries and milestones |
| Staff Notes | Internal notes on customers visible across the team |
| Customer Preferences | Per-customer communication, product, and service preferences |

---

## 7. Communication

| Feature | Description |
|---|---|
| Unified Inbox | All channels (email, SMS, WhatsApp, portal) in one thread view |
| Live Chat Widget | Real-time customer chat embedded in the portal |
| Chatbot / AI Assistant | Configurable chatbot handles FAQs before escalating to staff |
| Smart Reply Suggestions | AI suggests canned replies based on message content |
| Auto-Translation | Inbound/outbound messages auto-translated per customer locale |
| Conversation Sentiment | Sentiment analysis on threads; flags negative conversations |
| Read Receipts | Message delivery and read status in threaded conversations |

---

## 8. Trust & Safety

| Feature | Description |
|---|---|
| Verified Reviews | Two-sided reviews; only post-transaction reviews accepted |
| Staff Credentials | Upload and display certifications, licences, qualifications |
| Staff Portfolio | Photo gallery of work visible to customers pre-booking |
| Identity Verification | Document-based ID verification for high-trust bookings |
| Background Checks | Staff background check status tracked and surfaced |
| Dispute Resolution | Structured dispute flow with message thread and resolution tracking |
| Merchant Network Reviews | Share review reputation across franchise / network locations |
| Service Insurance | Per-booking damage and liability insurance purchases tracked |

---

## 9. AI & Automation

| Feature | Description |
|---|---|
| AI Action Cards | Rules-based dashboard cards: overdue invoices, low stock, follow-ups |
| AI Chat (GPT-4o) | Conversational assistant over business data; history in localStorage |
| AI Product Descriptions | Generate product descriptions from name, category, attributes |
| AI Email Drafts | Draft customer reply emails from conversation context |
| AI Photo Tagging | Auto-tag product and portfolio photos with searchable labels |
| AI Price Suggestions | Suggest selling prices from cost, margin target, and market data |
| AI Customer Personas | Generate a persona summary per customer from their history |
| AI Recommendations | Personalised cross-sell and upsell suggestions per customer |
| Voice Shortcuts | Siri / Google Assistant / Bixby shortcuts that query live business data |
| Voice Reports | Spoken-query reports ("today's revenue") resolved rule-based, zero GPT cost |
| Anomaly Alerts | Push notifications when KPIs diverge from expected ranges |

---

## 10. Reporting & Analytics

| Feature | Description |
|---|---|
| Dashboard | Key metrics: revenue, invoices, customers, bookings |
| Analytics Module | Trend charts, cohort views, top products and customers |
| Customer Statements | Period statements per customer; exportable PDF |
| Mobile KPI Dashboard | Owner-facing KPI cards optimised for phone screens |
| Voice Reports | Query revenue, bookings, refunds, customers by voice |
| Anomaly Detection | Automatic detection of unusual patterns with alert push |
| Marketing Attribution | Track which campaigns and channels produce highest-LTV customers |
| A/B Testing | Create and measure variants; track conversions per variant |
| NPS Surveys | Post-transaction satisfaction surveys with trend reporting |

---

## 11. Integrations

| Feature | Description |
|---|---|
| Fortnox | Bidirectional sync of invoices, customers, products with Fortnox ERP |
| Stripe (Payments) | Invoice payment links, webhooks, signature-verified events |
| Stripe (Billing) | SaaS subscription plans with Stripe Checkout |
| Zapier / Make | Every business event exposed as a trigger; 5,000+ app automations |
| Customer Webhooks | Customers configure their own HMAC-signed webhook endpoints |
| API Keys | Customers generate scoped API keys (`vf_` prefix, bcrypt-stored) |
| API Documentation Portal | Embedded Swagger UI + Redoc with auth guide and code snippets |
| Calendar (Google / Outlook / Apple) | Bidirectional booking sync; per-provider, per-user config |
| Google Analytics / Tag Manager | (Planned) Frontend instrumentation hooks |
| Supabase Auth | JWT-based authentication; portal JWTs issued separately |

---

## 12. Mobile-First Features

| Feature | Description |
|---|---|
| iOS / Android Home Screen Widgets | Today's bookings, revenue, low stock, alerts — native widget config |
| Widget Data Snapshots | 15-minute cached payload served from backend for fast widget reads |
| Apple Watch / Wear OS | Pair watch device, view today's schedule, mark booking complete |
| Siri Shortcuts | "Hey Siri, show me today's revenue" — spoken response from live data |
| Google Assistant Shortcuts | Same as Siri, for Android users |
| Lock Screen Alerts | Critical alerts (overdue invoice, low stock, cash warning) pre-unlock |
| Alert Severity Levels | Info / Warning / Critical with dismiss and dismiss-all |
| Command Palette (Cmd+K) | Universal fast search: customers, invoices, products, bookings |
| Dark Mode | Full dark theme with system preference detection and localStorage override |
| Notification Bundles | Group notifications by type; schedule digest emails (immediate/hourly/daily/weekly) |
| Timezone Auto-Switching | Per-location IANA timezone; reports displayed in local time |

---

## 13. Operations & Quality

| Feature | Description |
|---|---|
| SOP Library | Standard Operating Procedures with version history |
| Checklists | Create, assign, and track operational checklists |
| Recurring Reminders | Schedule recurring operational reminders for staff |
| Decision Log | Record and retrieve key business decisions with context |
| Compliance Calendar | Country-specific regulatory deadlines (VAT, annual return, etc.) |
| Regulatory Alerts | Proactive reminders for upcoming filing deadlines |

---

## 14. Multi-Entity & Franchise

| Feature | Description |
|---|---|
| Multi-Entity Consolidation | Parent + subsidiary structure with consolidated P&L |
| Intercompany Transfers | Track and eliminate intercompany transactions in reporting |
| Elimination Entries | Accounting-level eliminations for consolidated statements |
| Franchise Agreements | Track royalty rates, territory, and review dates per franchisee |
| Franchise Royalty Billing | Auto-calculate and invoice royalties from franchisee revenue |
| Franchise Catalog Push | Push product catalog updates from franchisor to all franchisees |

---

## 15. Finance & Accounting

| Feature | Description |
|---|---|
| General Ledger | Double-entry bookkeeping with chart of accounts |
| VAT Returns | Prepare and export VAT return data per reporting period |
| Fixed Assets | Asset register with depreciation schedules |
| Payroll (basic) | Staff payment records linked to org |
| Budget | Set and track budgets by category and period |
| Bank Reconciliation | Match imported bank transactions to invoices and expenses |

---

## 16. Team & Settings

| Feature | Description |
|---|---|
| Team Management | Invite members, assign roles (admin / manager / staff) |
| Role-Based Access | Every endpoint enforces org_id isolation; role checks per router |
| Organisation Profile | Name, address, logo, timezone, locale settings |
| Notification Preferences | Per-user channel and schedule preferences |
| Subscription Management | Upgrade, downgrade, view plan limits — Stripe-powered |
| Audit Log | (Planned) Immutable record of sensitive actions per org |

---

## 17. Developer & Platform

| Feature | Description |
|---|---|
| Public API | RESTful FastAPI — full Swagger UI at `/api/docs` |
| Customer API Keys | Scoped keys with `vf_` prefix, bcrypt-hashed, expiry-aware |
| Webhook Subscriptions | HMAC-SHA256 signed events, delivery history, secret rotation |
| Zapier / Make Triggers | Every key event published to registered hook URLs |
| Health Endpoint | `GET /api/health` verifies DB, returns version — monitored by UptimeRobot |
| i18n | English, Swedish, Norwegian, Danish, Arabic |
| Multi-locale Routing | `next-intl` with per-locale URL prefixes (`/en/`, `/sv/`, etc.) |

---

*Last updated: Sprint 15 — 2026-05-01*
*Total database tables: ~130 across 15 feature sprints*
