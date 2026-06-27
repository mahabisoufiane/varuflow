import React from 'react';
import { X } from 'lucide-react';

// ExitIntentModal only shows when mouse leaves viewport top edge — so we render
// the inner dialog card directly to capture its appearance in a static preview.
export function OpenState() {
  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px',
        background: 'rgba(0,0,0,0.70)',
        backdropFilter: 'blur(6px)',
        borderRadius: '12px',
        minHeight: '320px',
      }}
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '400px',
          borderRadius: '16px',
          border: '1px solid rgba(255,255,255,0.1)',
          padding: '32px',
          textAlign: 'center',
          background: '#141c2e',
        }}
      >
        <button
          style={{
            position: 'absolute',
            right: '16px',
            top: '16px',
            borderRadius: '50%',
            border: '1px solid rgba(255,255,255,0.1)',
            padding: '6px',
            color: '#64748b',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <X size={16} />
        </button>

        <div
          style={{
            margin: '0 auto 16px',
            display: 'flex',
            height: '48px',
            width: '48px',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>

        <h2 style={{ color: '#f1f5f9', fontSize: '20px', fontWeight: 700, margin: '0 0 12px' }}>
          Before you go…
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6, margin: '0 0 24px' }}>
          Start your 14-day Pro trial today — no credit card required, cancel anytime.
          Full access to all features from day one.
        </p>

        <a
          href="/trial"
          style={{
            display: 'block',
            width: '100%',
            borderRadius: '12px',
            padding: '12px',
            background: '#4f46e5',
            color: '#fff',
            fontWeight: 600,
            fontSize: '14px',
            textDecoration: 'none',
            marginBottom: '12px',
          }}
        >
          Start free trial
        </a>

        <button style={{ color: '#64748b', fontSize: '12px', background: 'transparent', border: 'none', cursor: 'pointer' }}>
          No thanks, I'll pay full price later
        </button>
      </div>
    </div>
  );
}
