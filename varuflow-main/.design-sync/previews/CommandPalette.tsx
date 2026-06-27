const navItems = [
  { label: 'Dashboard', group: 'Navigation' },
  { label: 'Analytics', group: 'Navigation' },
  { label: 'Inventory', group: 'Navigation' },
  { label: 'Invoices', group: 'Navigation' },
  { label: 'Cash Register', group: 'Navigation' },
  { label: 'Customers', group: 'Navigation' },
];

const searchResults = [
  { label: 'INV-2024-0142', sub: 'Eriksson & Partners · 12 500 kr', type: 'invoice', color: '#10b981' },
  { label: 'Anna Lindström', sub: 'Customer · anna@lindstrom.se', type: 'customer', color: '#8b5cf6' },
  { label: 'Trådlös mus', sub: 'Product · 12 in stock', type: 'product', color: '#3b82f6' },
];

export function Empty() {
  return (
    <div style={{ padding: '24px', background: '#0f1117', minHeight: '360px' }}>
      <div style={{
        background: '#1a1f2e', borderRadius: '12px', overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span style={{ color: '#6b7280', fontSize: '15px' }}>Search everything…</span>
        </div>
        <div style={{ padding: '8px' }}>
          <p style={{ fontSize: '11px', color: '#4b5563', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '8px 8px 4px', margin: 0 }}>Navigation</p>
          {navItems.map(item => (
            <div key={item.label} style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '10px 8px', borderRadius: '8px', cursor: 'pointer',
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2"><circle cx="12" cy="12" r="5" /></svg>
              <span style={{ fontSize: '14px', color: '#d1d5db' }}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function WithResults() {
  return (
    <div style={{ padding: '24px', background: '#0f1117', minHeight: '360px' }}>
      <div style={{
        background: '#1a1f2e', borderRadius: '12px', overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span style={{ color: '#e5e7eb', fontSize: '15px' }}>INV-2024</span>
        </div>
        <div style={{ padding: '8px' }}>
          <p style={{ fontSize: '11px', color: '#4b5563', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '8px 8px 4px', margin: 0 }}>Results</p>
          {searchResults.map((r, i) => (
            <div key={r.label} style={{
              display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 8px',
              borderRadius: '8px', background: i === 0 ? 'rgba(255,255,255,0.06)' : 'transparent',
              cursor: 'pointer',
            }}>
              <span style={{
                fontSize: '11px', padding: '2px 6px', borderRadius: '4px',
                background: r.color + '20', color: r.color,
              }}>{r.type}</span>
              <div>
                <div style={{ fontSize: '14px', color: '#e5e7eb', fontWeight: '500' }}>{r.label}</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>{r.sub}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
