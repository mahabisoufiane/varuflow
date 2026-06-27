/**
 * UpsellModal uses next/navigation hooks and Dialog from shadcn.
 * We render a static faithful reproduction of the modal chrome.
 */
import { Zap } from 'lucide-react';

function ModalShell({ title, message, cta, tier }: { title: string; message: string; cta: string; tier: string }) {
  return (
    <div style={{ position: 'relative', minHeight: '280px', background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', borderRadius: '12px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ width: '100%', maxWidth: '400px', background: '#fff', borderRadius: '12px', border: '1px solid #e5e7eb', padding: '24px', boxShadow: '0 20px 60px rgba(0,0,0,0.25)' }}>
        {/* Header */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Zap style={{ width: 20, height: 20, color: '#eab308' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#ca8a04' }}>
              Upgrade to {tier}
            </span>
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', margin: '0 0 8px', lineHeight: 1.3 }}>{title}</h2>
          <p style={{ fontSize: '14px', color: '#6b7280', margin: 0, lineHeight: 1.5 }}>{message}</p>
        </div>
        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
          <button style={{ height: '36px', padding: '0 16px', borderRadius: '8px', border: '1px solid #d1d5db', background: '#fff', fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#374151' }}>
            Maybe later
          </button>
          <button style={{ height: '36px', padding: '0 16px', borderRadius: '8px', border: 'none', background: '#1a2332', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>
            {cta}
          </button>
        </div>
      </div>
    </div>
  );
}

export function AdvancedAnalytics() {
  return (
    <ModalShell
      tier="PRO"
      title="Unlock advanced analytics"
      message="Get deeper insights into sales trends, cohort analysis, and forecasting. Available on the PRO plan."
      cta="Upgrade to PRO"
    />
  );
}

export function APIAccess() {
  return (
    <ModalShell
      tier="ENTERPRISE"
      title="REST API access included"
      message="Connect your systems directly to Varuflow. Automate invoicing, sync inventory and more via our full REST API."
      cta="Talk to sales"
    />
  );
}
