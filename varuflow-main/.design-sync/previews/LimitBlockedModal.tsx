import { LimitBlockedModal } from 'varuflow-ui';

/**
 * LimitBlockedModal uses next/navigation useRouter, so we render it inside
 * a container that shows the dialog directly (open=true).
 * The modal renders inside a Dialog which is portaled — we show the shell inline.
 */

export function ProductsBlocked() {
  return (
    <div style={{ position: 'relative', minHeight: '300px', background: '#f9fafb', borderRadius: '12px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: '100%', maxWidth: '420px', background: '#fff', borderRadius: '12px', border: '1px solid #e5e7eb', padding: '24px', boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
        {/* Header */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', marginBottom: '8px' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span style={{ fontWeight: 600, fontSize: '16px' }}>Plan limit reached</span>
          </div>
          <p style={{ fontSize: '14px', color: '#6b7280', lineHeight: 1.5, margin: 0 }}>
            Your <strong>Starter</strong> plan allows up to <strong>50</strong> products. You currently have <strong>50</strong>. Upgrade your plan to add more.
          </p>
        </div>
        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '8px' }}>
          <button style={{ height: '36px', padding: '0 16px', borderRadius: '8px', border: '1px solid #d1d5db', background: '#fff', fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#374151' }}>
            Cancel
          </button>
          <button style={{ height: '36px', padding: '0 16px', borderRadius: '8px', border: 'none', background: '#dc2626', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>
            Upgrade plan
          </button>
        </div>
      </div>
    </div>
  );
}

export function InvoicesBlocked() {
  return (
    <div style={{ position: 'relative', minHeight: '300px', background: '#f9fafb', borderRadius: '12px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: '100%', maxWidth: '420px', background: '#fff', borderRadius: '12px', border: '1px solid #e5e7eb', padding: '24px', boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', marginBottom: '8px' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span style={{ fontWeight: 600, fontSize: '16px' }}>Plan limit reached</span>
          </div>
          <p style={{ fontSize: '14px', color: '#6b7280', lineHeight: 1.5, margin: 0 }}>
            Your <strong>Basic</strong> plan allows up to <strong>100</strong> invoices per month. You currently have <strong>100</strong>. Upgrade your plan to add more.
          </p>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '8px' }}>
          <button style={{ height: '36px', padding: '0 16px', borderRadius: '8px', border: '1px solid #d1d5db', background: '#fff', fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#374151' }}>Cancel</button>
          <button style={{ height: '36px', padding: '0 16px', borderRadius: '8px', border: 'none', background: '#dc2626', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>Upgrade plan</button>
        </div>
      </div>
    </div>
  );
}
