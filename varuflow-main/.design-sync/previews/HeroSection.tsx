import React from 'react';

// HeroSection uses <Link> from @/i18n/navigation (Next.js router) which requires
// Next.js context not available in the static preview bundle. We replicate the
// component's visual output with plain HTML to capture the design faithfully.

function HeroPreview({
  eyebrow,
  headline,
  subheadline,
  ctaPrimary,
  ctaSecondary,
}: {
  eyebrow?: string;
  headline: string;
  subheadline: string;
  ctaPrimary: { href: string; label: string };
  ctaSecondary?: { href: string; label: string };
}) {
  return (
    <section
      style={{
        position: 'relative',
        overflow: 'hidden',
        padding: '96px 16px',
        textAlign: 'center',
        background:
          'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(37,99,235,0.18) 0%, transparent 70%), #0d1526',
      }}
    >
      <div style={{ position: 'relative', margin: '0 auto', maxWidth: '768px' }}>
        {eyebrow && (
          <p
            style={{
              display: 'inline-block',
              borderRadius: '9999px',
              border: '1px solid rgba(99,102,241,0.3)',
              background: 'rgba(99,102,241,0.1)',
              padding: '4px 16px',
              fontSize: '11px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              color: '#818cf8',
              marginBottom: '16px',
            }}
          >
            {eyebrow}
          </p>
        )}

        <h1
          style={{
            color: '#f1f5f9',
            fontSize: '48px',
            fontWeight: 800,
            lineHeight: 1.1,
            letterSpacing: '-0.03em',
            margin: '0 0 24px',
          }}
        >
          {headline}
        </h1>

        <p
          style={{
            color: '#94a3b8',
            fontSize: '18px',
            lineHeight: 1.65,
            maxWidth: '672px',
            margin: '0 auto 40px',
          }}
        >
          {subheadline}
        </p>

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
          }}
        >
          <a
            href={ctaPrimary.href}
            style={{
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
    <HeroPreview
      eyebrow="Built for Nordic SMBs"
      headline="The Business OS for modern wholesale & distribution"
      subheadline="Invoicing, inventory, CRM, HR, and analytics — all in one place. Compliant with Swedish BAS, Norwegian SAF-T, and Danish momsreglerne."
      ctaPrimary={{ href: '/trial', label: 'Start 14-day free trial' }}
      ctaSecondary={{ href: '/demo', label: 'Watch a 3-min demo' }}
    />
  );
}

export function NoEyebrow() {
  return (
    <HeroPreview
      headline="Run your entire business from one screen"
      subheadline="Replace five disconnected tools with Varuflow. Most customers go live in under an hour."
      ctaPrimary={{ href: '/trial', label: 'Get started free' }}
    />
  );
}
