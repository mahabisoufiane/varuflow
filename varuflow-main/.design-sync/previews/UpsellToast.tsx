/**
 * UpsellToast is a side-effect-only component (renders null, fires sonner toast).
 * We show a realistic static reproduction of the toast notification it would produce.
 */
import { Zap, X } from 'lucide-react';

function ToastPreview({ message, cta }: { message: string; cta: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
      gap: '12px', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px',
      padding: '14px 16px', boxShadow: '0 4px 20px rgba(0,0,0,0.12)', maxWidth: '360px',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', flex: 1 }}>
        <Zap style={{ width: 18, height: 18, color: '#eab308', marginTop: '1px', flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: '14px', color: '#111827', margin: '0 0 8px', lineHeight: 1.4 }}>{message}</p>
          <button style={{ fontSize: '13px', fontWeight: 600, color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', textUnderlineOffset: '2px' }}>
            {cta}
          </button>
        </div>
      </div>
      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 0, flexShrink: 0 }}>
        <X style={{ width: 16, height: 16 }} />
      </button>
    </div>
  );
}

export function MilestoneToast() {
  return (
    <div style={{ padding: '24px', background: '#f9fafb', borderRadius: '12px' }}>
      <p style={{ fontSize: '11px', color: '#9ca3af', margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Toast notification (bottom-right)</p>
      <ToastPreview
        message="You've sent 80 invoices this month — only 20 left on your current plan."
        cta="Upgrade for unlimited invoices →"
      />
    </div>
  );
}

export function FeatureDiscoveryToast() {
  return (
    <div style={{ padding: '24px', background: '#f9fafb', borderRadius: '12px' }}>
      <p style={{ fontSize: '11px', color: '#9ca3af', margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Toast notification (bottom-right)</p>
      <ToastPreview
        message="Unlock white-label branding and let customers see your logo everywhere."
        cta="See PRO features →"
      />
    </div>
  );
}

export function RendersNull() {
  return (
    <div style={{ padding: '16px', background: '#fef9c3', borderRadius: '8px', border: '1px solid #fde047', fontFamily: 'system-ui, sans-serif' }}>
      <p style={{ fontSize: '13px', color: '#713f12', margin: 0 }}>
        <strong>Note:</strong> UpsellToast renders <code>null</code> — it fires a Sonner toast as a side effect on mount. The previews above are static reproductions of the toast it would trigger.
      </p>
    </div>
  );
}
