import React from 'react';
import { X } from 'lucide-react';

// NpsSurveyModal renders as a fixed bottom-right widget and requires callbacks + API.
// We render the inner card structure statically in open state for design review.
export function OpenSurvey() {
  const scores = Array.from({ length: 11 }, (_, i) => i);

  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '400px' }}>
      <div
        style={{
          background: '#0f172a',
          border: '1px solid rgba(99,102,241,0.3)',
          borderRadius: '12px',
          boxShadow: '0 25px 50px rgba(99,102,241,0.1)',
          padding: '20px',
          position: 'relative',
        }}
      >
        {/* Glow ring */}
        <div style={{ position: 'absolute', inset: 0, borderRadius: '12px', boxShadow: 'inset 0 0 0 1px rgba(99,102,241,0.2)', pointerEvents: 'none' }} />

        {/* Close */}
        <button style={{ position: 'absolute', top: '12px', right: '12px', color: '#94a3b8', background: 'transparent', border: 'none', cursor: 'pointer' }}>
          <X size={16} />
        </button>

        <p style={{ fontSize: '11px', fontWeight: 600, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
          Quick question
        </p>

        <p style={{ fontSize: '14px', color: '#e2e8f0', fontWeight: 500, marginBottom: '16px', paddingRight: '20px' }}>
          How likely are you to recommend Varuflow to a colleague?
        </p>

        {/* Score buttons */}
        <div style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
          {scores.map((i) => (
            <button
              key={i}
              style={{
                flex: 1,
                padding: '6px 0',
                fontSize: '11px',
                fontWeight: 600,
                borderRadius: '4px',
                border: 'none',
                cursor: 'pointer',
                background: i === 8 ? '#4f46e5' : '#1e293b',
                color: i === 8 ? '#fff' : '#94a3b8',
                boxShadow: i === 8 ? '0 0 0 2px #818cf8' : 'none',
              }}
            >
              {i}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#64748b', marginBottom: '16px' }}>
          <span>Not at all</span>
          <span>Definitely</span>
        </div>

        <button
          style={{
            width: '100%',
            padding: '8px',
            borderRadius: '8px',
            background: '#4f46e5',
            color: '#fff',
            fontWeight: 600,
            fontSize: '14px',
            border: 'none',
            cursor: 'pointer',
            marginBottom: '8px',
          }}
        >
          Submit feedback
        </button>
        <button style={{ width: '100%', textAlign: 'center', fontSize: '12px', color: '#64748b', background: 'transparent', border: 'none', cursor: 'pointer' }}>
          Dismiss
        </button>
      </div>
    </div>
  );
}

export function ThankYouPromoter() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '400px' }}>
      <div
        style={{
          background: '#0f172a',
          border: '1px solid rgba(99,102,241,0.3)',
          borderRadius: '12px',
          padding: '20px',
        }}
      >
        <p style={{ fontSize: '14px', fontWeight: 600, color: '#e2e8f0', marginBottom: '12px' }}>
          🎉 Thank you! Would you leave us a quick review?
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          <a
            href="#"
            style={{ flex: 1, padding: '8px', textAlign: 'center', fontSize: '12px', fontWeight: 600, borderRadius: '8px', background: '#4f46e5', color: '#fff', textDecoration: 'none' }}
          >
            Review on G2
          </a>
          <a
            href="#"
            style={{ flex: 1, padding: '8px', textAlign: 'center', fontSize: '12px', fontWeight: 600, borderRadius: '8px', background: '#1e293b', color: '#e2e8f0', textDecoration: 'none' }}
          >
            Review on Capterra
          </a>
        </div>
      </div>
    </div>
  );
}
