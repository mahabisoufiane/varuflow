# Content Production Workflow — Varuflow Blog

## Overview

This document defines the end-to-end workflow for producing, publishing, and distributing blog content at Varuflow. All team members involved in content should read and follow this document.

**Content stack:** Sanity CMS → Next.js ISR → Vercel CDN

---

## 1. Topic Research

### Tools
- **Ahrefs** — keyword difficulty, search volume, competitor gap analysis
- **SEMrush** — SERP analysis, topic clusters
- **Sanity Vision** — GROQ queries to audit existing coverage gaps

### Process
1. Monthly keyword audit: pull top 50 keywords for our target markets (SE compliance, SA e-invoicing, Nordic wholesale)
2. Score each topic: Search Volume × (1 - KD/100) × Business Value
3. Prioritise topics in three categories:
   - **Pillar pages** (1,500–3,000 words, monthly) — target KD < 40
   - **Supporting posts** (800–1,200 words, weekly) — target KD < 25
   - **News/updates** (300–500 words, as-needed) — reactive

### Topic brief template
```
Title:
Target keyword (primary):
Supporting keywords (3-5):
Search intent: [informational / navigational / transactional]
Estimated difficulty (1-10):
Business value (1-10): 
Target word count:
Target locale(s):
Competitor articles to outdo (URLs):
Required internal links (3-5):
Required external links (authoritative sources):
Lead magnet opportunity? Y/N
```

---

## 2. Outline Approval

**Owner:** Content Lead (Sara Lindqvist)

All articles must have an approved outline before writing begins. Outline includes:

1. Working title and target keyword
2. H2 structure (main sections) with key points per section
3. Data points and citations planned
4. Internal linking plan
5. Lead magnet plan (if applicable)
6. CTA at article end
7. Estimated word count per section

**Approval:** Content Lead reviews for:
- Keyword fit and intent match
- Factual accuracy (especially compliance content)
- Internal linking strategy
- Lead magnet relevance

Outlines should be approved within 2 business days of submission.

---

## 3. Writing

**Style guide:**
- Write for the operator, not the accountant
- Use active voice ("Do X" not "X should be done")
- Short paragraphs (3–5 sentences max)
- Every claim needs a source in brackets [source URL] — reviewed during editorial
- Use H2 for main sections, H3 for subsections — IDs must match tableOfContents in seed
- Tables for comparisons (3+ items)
- Blockquote for important callouts or stats
- Include the article's target keyword in: title, first H2, first paragraph, meta description
- Minimum 3 internal links per article

**Compliance content (special rules):**
- Every regulation reference must cite the specific law/section (e.g., "Bokföringslagen 5 kap. 6§")
- Every statement about what "you must do" must be verified against the primary source
- Include "last verified by [name] on [date]" note at the end
- Never give legal advice — use "consult with a qualified advisor for your specific situation"

**Word count targets:**
- Pillar: 1,500–2,500 words
- Supporting: 800–1,200 words
- News: 300–500 words

---

## 4. Editorial Review

**Owner:** Content Lead

Checklist before editorial approval:
- [ ] All citations sourced and linked (external links to official sources)
- [ ] Compliance statements verified against primary legislation
- [ ] No generic filler paragraphs
- [ ] Lead magnet topic matches article content
- [ ] CTA is relevant and specific (not generic "try Varuflow")
- [ ] Tables and lists formatted correctly
- [ ] Author bio is accurate and current
- [ ] `bodyHtml` IDs match `tableOfContents` array in the seed/Sanity doc
- [ ] `seoTitle` ≤ 60 characters
- [ ] `seoDescription` ≤ 155 characters
- [ ] `publishedAt` and `updatedAt` are correct dates

Editorial turnaround: 3 business days for new articles, 1 business day for updates.

---

## 5. SEO Optimization (Surfer SEO / Manual Review)

After editorial approval:

1. **Surfer SEO analysis:**
   - Target article score: ≥ 70/100
   - Check NLP terms coverage (missing terms flagged in Surfer)
   - Verify H2 structure matches top-ranking page structures

2. **Manual checks:**
   - Target keyword: in title, H1, first paragraph, at least one H2
   - Image alt text: descriptive, includes keyword where natural
   - Internal links: 3–5 per article, anchor text is descriptive (not just "click here")
   - External links: 1–2 to authoritative sources (riksdagen.se, skatteverket.se, zatca.gov.sa, peppol.eu)
   - Mobile preview in Chrome DevTools: article readable on 375px width

3. **Internationalization:**
   - For EN/SV pairs: ensure `translationSlug` is set in both directions
   - Hreflang will be auto-generated from metadata if `translationSlug` is set
   - For Arabic content: verify RTL rendering in article page

---

## 6. Publication

### Sanity CMS workflow
1. Create post in Sanity Studio (`cd studio && npm run dev`)
2. Fill all required fields (title, slug, locale, category, author, publishedAt)
3. Add body in portable text format
4. Set `leadMagnet` if applicable
5. Add related articles (up to 4)
6. Set `seoTitle` and `seoDescription`
7. Set canonical URL only if different from auto-generated
8. Publish in Sanity (saves to Sanity Cloud)
9. Trigger ISR revalidation: `revalidate` is set to 3600 seconds — Next.js will pick up new content within 1 hour automatically. For immediate updates, trigger a manual Vercel revalidation.

### For seed data (local dev / before Sanity configured)
Add the article to `frontend/src/lib/sanity/seed/posts.ts` following the existing structure. The blog will serve seed data until `NEXT_PUBLIC_SANITY_PROJECT_ID` is set.

### Environment variable checklist before first Sanity go-live
```
# Vercel (frontend)
NEXT_PUBLIC_SANITY_PROJECT_ID=your-project-id
NEXT_PUBLIC_SANITY_DATASET=production
NEXT_PUBLIC_SITE_URL=https://varuflow.vercel.app

# Ensure these are already set:
NEXT_PUBLIC_API_URL=https://varuflow-production.up.railway.app
```

---

## 7. Distribution

### Immediately after publishing (Day 0)
- [ ] Share on LinkedIn (company page + personal profile of author if willing)
- [ ] Share on X/Twitter with article preview card (OG image auto-generated)
- [ ] Add to newsletter queue (Resend audience — next weekly digest)
- [ ] Post in relevant Slack communities (Nordic founder/entrepreneur channels)
- [ ] Submit URL to IndexNow for faster Google indexing

### LinkedIn post template
```
I just wrote about [topic].

The short version: [1-2 sentence summary]

The longer version is on the Varuflow blog — link in first comment.

[1 engaging question to drive comments]

#compliance #NordicBusiness #[specific tag]
```

### Newsletter announcement template
Subject: "New guide: [article title]"
Body: excerpt + "Read the full guide →" CTA + lead magnet offer if applicable

---

## 8. Update Cycle (Every 6 Months)

All evergreen articles should be reviewed every 6 months for:
- Legislative changes (Skatteverket guidance, ZATCA updates, GDPR rulings)
- Accuracy of pricing information in comparison articles
- Dead links (external references)
- SEO performance: if article ranking fell, consider rewrite or internal link boost
- New internal linking opportunities (newly published related articles)

### Update checklist
- [ ] Review Skatteverket, IMY, ZATCA, IFRS news for changes
- [ ] Update `updatedAt` date in Sanity / seed data
- [ ] Add "Last updated: [date]" note to article header
- [ ] Check all external URLs are still live (301/404 detection)
- [ ] Review Google Search Console for queries the article ranks for but doesn't mention — incorporate them
- [ ] Update comparison tables with current competitor pricing

---

## 9. Lead Magnet System

### PDF creation
Lead magnets are prepared as PDF checklists or templates and stored at:
`frontend/public/downloads/[pdfSlug].pdf`

Follow the naming convention in `leadMagnet.pdfSlug` in the seed data.

### Conversion tracking
The `LeadMagnetForm` component submits to `/api/waitlist/signup` with:
- `email` — subscriber email
- `source` — `lead_magnet_{pdfSlug}` (identifies origin)
- `tags` — `["lead_magnet", pdfSlug]`

In Resend, configure an automation sequence triggered by `source: lead_magnet_*`:
1. **Day 0:** Deliver PDF download link (auto-sent by the form's "done" state — link points to `/downloads/{pdfSlug}.pdf`)
2. **Day 3:** Follow-up email: "Did the checklist help? Here are 3 more compliance tips..."
3. **Day 7:** Product CTA: "We built Varuflow to handle this automatically — [try free]"
4. **Day 14:** Case study or testimonial email
5. **Day 21:** Final CTA or unsubscribe prompt

### Conversion funnel (to track in PostHog)
```
blog_article_view → lead_magnet_view → lead_magnet_submit → trial_start → paid_conversion
```

Events to log:
- `blog_article_view` — on blog article page load
- `lead_magnet_view` — when LeadMagnetForm is in viewport (IntersectionObserver)
- `lead_magnet_submit` — on form submit success
- `blog_cta_click` — on article-end CTA click

---

## 10. Metrics and KPIs

Track monthly in Ahrefs + Google Search Console + PostHog:

| Metric | Target | Owner |
|--------|--------|-------|
| Organic sessions (blog) | +20% MoM | Content Lead |
| Average position (target keywords) | Top 10 | Content Lead |
| Lead magnet conversion rate | ≥ 8% of readers | Marketing |
| Trial signups from blog | ≥ 15% of leads | Marketing |
| Articles published per month | ≥ 2 pillar + 4 supporting | Content Lead |
| Average word count per pillar | 1,800+ | Content Lead |

---

*Last updated: 2026-05-02 — Sara Lindqvist, Compliance Lead*
