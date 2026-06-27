import React from 'react';

// CTABanner uses <Link> from @/i18n/navigation (Next.js router) which requires
// Next.js context not available in the static preview bundle. We replicate the
// component's visual output with plain HTML to capture the design faithfully.

function CTABannerPreview({
  headline,
  subheadline,
  ctaPrimary,
  ctaSecondary,
}: {
  headline: string;
  subheadline?: string;
  ctaPrimary: { href: string; label: string };
  ctaSecondary?: { href: string; label: string };
}) {
  return (
    <section
      style={{
        position: 'relative',
        overflow: 'hidden',
        padding: '80px 16px',
        textAlign: 'center',
        background:
          'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(37,99,235,0.15) 0%, transparent 70%), #0d1526',
      }}
    >
      <div style={{ margin: '0 auto', maxWidth: '672px' }}>
        <h2
          style={{
            color: '#f1f5f9',
            fontSize: '36px',
            fontWeight: 800,
            letterSpacing: '-0.02em',
            lineHeight: 1.15,
            margin: '0 0 16px',
          }}
        >
          {headline}
        </h2>
        {subheadline && (
          <p
            style={{
              color: '#94a3b8',
              fontSize: '16px',
              lineHeight: 1.65,
              margin: '0 auto 32px',
              maxWidth: '576px',
            }}
          >
            {subheadline}
          </p>
        )}

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            marginTop: '8px',
          }}
        >
          <a
            href={ctaPrimary.href}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              borderRadius: '12px',
              padding: '12px 28px',
              fontSize: '16px',
              fontWeight: 600,
              background: '#4f46e5',
              color: '#fff',
              textDecoration: 'none',
            }}
          >
            {ctaPrimary.label}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </a>
          {ctaSecondary && (
            <a
              href={ctaSecondary.href}
              style={{
                borderRadius: '12px',
                padding: '12px 28px',
                fontSize: '16px',
                fontWeight: 600,
                color: '#94a3b8',
                border: '1px solid rgba(255,255,255,0.15)',
                textDecoration: 'none',
                background: 'transparent',
              }}
            >
              {ctaSecondary.label}
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

export function Default() {
  return (
    <CTABannerPreview
      headline="Ready to grow your Nordic business?"
      subheadline="Join 2,000+ SMBs who manage invoicing, inventory, and customers in one place. Start free for 14 days — no credit card required."
      ctaPrimary={{ href: '/trial', label: 'Start free trial' }}
      ctaSecondary={{ href: '/demo', label: 'Book a demo' }}
    />
  );
}

export function Minimal() {
  return (
    <CTABannerPreview
      headline="Start your 14-day free trial today"
      ctaPrimary={{ href: '/trial', label: 'Get started free' }}
    />
  );
}
