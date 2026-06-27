import React from 'react';
import { Sparkles, X } from 'lucide-react';

// UpgradePromptInline uses useRouter + useParams from next/navigation and imports
// Button from @/components/ui/button. Both require Next.js context unavailable in
// the static preview bundle. We replicate the component's visual output with
// plain HTML/inline styles.

function InlinePrompt({ message, cta }: { message: string; cta: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        borderRadius: '8px',
        border: '1px solid #bfdbfe',
        background: '#eff6ff',
        padding: '12px',
        fontSize: '14px',
        color: '#1e40af',
      }}
    >
      <Sparkles size={16} color="#6366f1" style={{ marginTop: '2px', flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 4px', lineHeight: 1.4 }}>{message}</p>
        <button
          style={{
            background: 'transparent',
            border: 'none',
            padding: 0,
            color: '#3730a3',
            fontWeight: 500,
            fontSize: '14px',
            cursor: 'pointer',
          }}
        >
          {cta} →
        </button>
      </div>
      <button
        aria-label="Dismiss"
        style={{
          background: 'transparent',
          border: 'none',
          padding: '2px',
          color: '#93c5fd',
          cursor: 'pointer',
        }}
      >
        <X size={14} />
      </button>
    </div>
  );
}

export function Default() {
  return (
    <div style={{ padding: '24px', background: '#f8fafc', borderRadius: '12px', maxWidth: '480px' }}>
      <InlinePrompt
        message="Unlock real-time analytics, revenue trend charts, and customer LTV reports on the Professional plan."
        cta="Upgrade to Professional"
      />
    </div>
  );
}

export function ApiAccessPrompt() {
  return (
    <div style={{ padding: '24px', background: '#f8fafc', borderRadius: '12px', maxWidth: '480px' }}>
      <InlinePrompt
        message="API access is available on the Enterprise plan. Connect Varuflow to your own systems via REST or webhooks."
        cta="Upgrade to Enterprise"
      />
    </div>
  );
}
