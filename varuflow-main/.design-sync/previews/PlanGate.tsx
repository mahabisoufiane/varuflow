import React from 'react';
import { Lock } from 'lucide-react';

// PlanGate uses <Link> from @/i18n/navigation (Next.js router) in the lock overlay.
// We replicate the locked state visually with plain HTML, and the unlocked state
// using the actual PlanGate component (which just renders children directly).
import { PlanGate } from 'varuflow-ui';

function AnalyticsContent() {
  return (
    <div style={{ padding: '24px', background: '#1e293b', borderRadius: '8px' }}>
      <h3 style={{ color: '#f1f5f9', fontSize: '16px', fontWeight: 600, margin: '0 0 8px' }}>Advanced Analytics</h3>
      <p style={{ color: '#94a3b8', fontSize: '14px', margin: '0 0 12px' }}>Revenue trends, customer LTV, product velocity reports.</p>
      <div style={{ height: '80px', background: '#334155', borderRadius: '6px' }} />
    </div>
  );
}

// Locked: replicate the component's lock overlay directly with inline styles
export function Locked() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '440px' }}>
      <div style={{ position: 'relative' }}>
        {/* Blurred preview */}
        <div style={{ pointerEvents: 'none', userSelect: 'none', opacity: 0.3, filter: 'blur(2px) grayscale(1)' }}>
          <AnalyticsContent />
        </div>
        {/* Lock overlay */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '12px',
            gap: '12px',
            padding: '16px',
            background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(4px)',
          }}
        >
          <div
            style={{
              display: 'flex',
              height: '48px',
              width: '48px',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '50%',
              border: '1px solid rgba(99,102,241,0.3)',
              background: 'rgba(99,102,241,0.2)',
            }}
          >
            <Lock size={20} color="#818cf8" />
          </div>
          <p style={{ fontSize: '14px', fontWeight: 600, color: '#fff', textAlign: 'center', margin: 0 }}>
            Advanced Analytics
          </p>
          <p style={{ fontSize: '12px', color: '#94a3b8', textAlign: 'center', maxWidth: '220px', margin: 0 }}>
            Available on the <span style={{ textTransform: 'capitalize', fontWeight: 500, color: '#a5b4fc' }}>professional</span> plan and above.
          </p>
          <a
            href="/pricing"
            style={{
              marginTop: '4px',
              borderRadius: '12px',
              background: '#4f46e5',
              padding: '8px 16px',
              fontSize: '14px',
              fontWeight: 600,
              color: '#fff',
              textDecoration: 'none',
            }}
          >
            Upgrade Plan
          </a>
        </div>
      </div>
    </div>
  );
}

export function Unlocked() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '440px' }}>
      <PlanGate
        requiredPlan="professional"
        userPlan="professional"
        featureName="Advanced Analytics"
      >
        <AnalyticsContent />
      </PlanGate>
    </div>
  );
}
