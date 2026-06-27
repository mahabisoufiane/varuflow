import React from 'react';
import { ArrowRight, X } from 'lucide-react';

// UpsellBanner uses useRouter + useParams from next/navigation and imports
// Button from @/components/ui/button. Both require Next.js context unavailable
// in the static preview bundle. We replicate the component's visual output.

function BannerPreview({ message, cta }: { message: string; cta: string }) {
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        borderRadius: '6px',
        border: '1px solid #fcd34d',
        background: '#fefce8',
        padding: '10px 16px',
        fontSize: '14px',
        color: '#92400e',
      }}
    >
      <span style={{ flex: 1, lineHeight: 1.4 }}>{message}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
        <button
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            background: 'transparent',
            border: 'none',
            color: '#b45309',
            fontWeight: 500,
            fontSize: '14px',
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: '4px',
          }}
        >
          {cta}
          <ArrowRight size={14} />
        </button>
        <button
          aria-label="Dismiss"
          style={{
            background: 'transparent',
            border: 'none',
            padding: '2px',
            color: '#d97706',
            cursor: 'pointer',
          }}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

export function Default() {
  return (
    <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '12px' }}>
      <BannerPreview
        message="You've used 4 of your 5 free seats. Upgrade to Professional to add unlimited team members."
        cta="Upgrade now"
      />
    </div>
  );
}

export function StorageBanner() {
  return (
    <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '12px' }}>
      <BannerPreview
        message="You're approaching your 500-product limit on the Starter plan. Upgrade to Professional for up to 10,000 products."
        cta="See Professional plan"
      />
    </div>
  );
}
