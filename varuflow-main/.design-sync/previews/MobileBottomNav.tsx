const tabs = [
  { label: 'Home', active: true },
  { label: 'Inventory', active: false },
  { label: 'Invoices', active: false },
  { label: 'POS', active: false },
  { label: 'More', active: false },
];

export function BottomNav() {
  return (
    <div style={{ maxWidth: '375px' }}>
      <nav style={{
        display: 'flex', borderTop: '1px solid #e5e7eb', background: '#fff',
        boxShadow: '0 -4px 10px -4px rgba(0,0,0,0.08)',
      }}>
        {tabs.map(tab => (
          <button key={tab.label} type="button" style={{
            flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: '2px', padding: '10px 4px', minHeight: '56px',
            border: 'none', background: 'transparent', cursor: 'pointer',
            color: tab.active ? '#2d6a4f' : '#6b7280', fontSize: '11px', fontWeight: '500',
            position: 'relative',
          }}>
            {tab.active && (
              <span style={{
                position: 'absolute', top: '4px', width: '4px', height: '4px',
                borderRadius: '50%', background: '#2d6a4f',
              }} />
            )}
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
            </svg>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

export function WithMoreDrawer() {
  const items = ['Analytics', 'Customers', 'AI', 'Settings', 'Recurring'];
  return (
    <div style={{ maxWidth: '375px' }}>
      <div style={{
        background: '#fff', borderRadius: '16px 16px 0 0', paddingBottom: '16px',
        boxShadow: '0 -8px 30px rgba(0,0,0,0.12)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
          <span style={{ width: '32px', height: '4px', borderRadius: '2px', background: '#d1d5db' }} />
        </div>
        <ul style={{ listStyle: 'none', margin: 0, padding: '0 8px' }}>
          {items.map(m => (
            <li key={m} style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '12px', borderRadius: '8px', minHeight: '56px',
            }}>
              <span style={{
                display: 'flex', width: '40px', height: '40px', alignItems: 'center',
                justifyContent: 'center', borderRadius: '12px', background: '#f3f4f6',
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2"><circle cx="12" cy="12" r="5" /></svg>
              </span>
              <span style={{ fontSize: '14px', fontWeight: '500', color: '#111827' }}>{m}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
