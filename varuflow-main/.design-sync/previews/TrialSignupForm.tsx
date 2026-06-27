import React from 'react';

// TrialSignupForm uses useRouter + useParams from next/navigation (Next.js App Router),
// which aren't available in the static preview bundle. We replicate the form's
// visual output with plain HTML/inline styles.

export function Default() {
  return (
    <div style={{ padding: '32px', background: '#0d1526', borderRadius: '12px' }}>
      <div style={{ textAlign: 'center', marginBottom: '24px' }}>
        <h2 style={{ color: '#f1f5f9', fontSize: '22px', fontWeight: 700, margin: '0 0 8px' }}>
          Start your free 14-day trial
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '14px', margin: 0 }}>
          Full Pro access · No credit card required · Cancel anytime
        </p>
      </div>

      <form style={{ maxWidth: '448px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', color: '#94a3b8', fontSize: '12px', fontWeight: 500, marginBottom: '6px' }}>
            Work email
          </label>
          <input
            type="email"
            placeholder="you@company.com"
            readOnly
            style={{
              width: '100%',
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.12)',
              padding: '12px 16px',
              fontSize: '14px',
              background: 'rgba(255,255,255,0.04)',
              color: '#94a3b8',
              boxSizing: 'border-box',
              outline: 'none',
            }}
          />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', color: '#94a3b8', fontSize: '12px', fontWeight: 500, marginBottom: '6px' }}>
            Password (min. 8 characters)
          </label>
          <input
            type="password"
            placeholder="Create a password"
            readOnly
            style={{
              width: '100%',
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.12)',
              padding: '12px 16px',
              fontSize: '14px',
              background: 'rgba(255,255,255,0.04)',
              color: '#94a3b8',
              boxSizing: 'border-box',
              outline: 'none',
            }}
          />
        </div>

        <button
          type="button"
          style={{
            width: '100%',
            borderRadius: '12px',
            padding: '12px',
            fontSize: '14px',
            fontWeight: 600,
            background: '#4f46e5',
            color: '#fff',
            border: 'none',
            cursor: 'pointer',
            marginBottom: '12px',
          }}
        >
          Start 14-day free trial — no card required
        </button>

        <p style={{ textAlign: 'center', color: '#64748b', fontSize: '12px', margin: 0 }}>
          No credit card required · Cancel anytime · Full Pro access
        </p>
      </form>
    </div>
  );
}
