// QuickActionSheet depends on next-intl, next/navigation, lucide-react,
// and live API calls. We render a static replica of the menu state
// so the visual design is captured without the hooks.

export function Default() {
  const actions = [
    { label: 'Add stock movement', color: '#DBEAFE', textColor: '#1D4ED8', icon: '📦' },
    { label: 'New quick invoice', color: '#F3E8FF', textColor: '#7C3AED', icon: '🧾' },
    { label: 'Scan product', color: '#ECFDF5', textColor: '#059669', icon: '🔍' },
    { label: 'Quick POS sale', color: '#FFF7ED', textColor: '#C2410C', icon: '🛒' },
    { label: 'Record payment', color: '#FEF9C3', textColor: '#A16207', icon: '💳' },
  ];

  return (
    <div style={{ maxWidth: '360px', background: '#fff', borderRadius: '16px', boxShadow: '0 4px 24px rgba(0,0,0,0.12)', overflow: 'hidden' }}>
      <div style={{ padding: '8px' }}>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, borderTop: '1px solid #F3F4F6' }}>
          {actions.map((a) => (
            <li key={a.label} style={{ borderBottom: '1px solid #F3F4F6' }}>
              <button
                type="button"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  width: '100%',
                  minHeight: '56px',
                  padding: '12px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '40px',
                    height: '40px',
                    borderRadius: '12px',
                    background: a.color,
                    fontSize: '18px',
                    flexShrink: 0,
                  }}
                >
                  {a.icon}
                </span>
                <span style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>
                  {a.label}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function StockMovementView() {
  return (
    <div style={{ maxWidth: '360px', background: '#fff', borderRadius: '16px', boxShadow: '0 4px 24px rgba(0,0,0,0.12)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #F3F4F6', padding: '12px' }}>
        <span style={{ fontSize: '14px', color: '#6B7280', fontWeight: 500 }}>← Back</span>
      </div>
      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <input
          placeholder="Search product…"
          style={{ height: '48px', width: '100%', borderRadius: '8px', border: '1px solid #D1D5DB', padding: '0 12px', fontSize: '14px', boxSizing: 'border-box' }}
          readOnly
        />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <button style={{ height: '48px', borderRadius: '8px', border: '1px solid #059669', background: '#059669', color: '#fff', fontSize: '14px', fontWeight: 500 }}>IN</button>
          <button style={{ height: '48px', borderRadius: '8px', border: '1px solid #E5E7EB', background: '#fff', fontSize: '14px', fontWeight: 500 }}>OUT</button>
        </div>
        <input
          type="number"
          defaultValue={1}
          style={{ height: '48px', width: '100%', borderRadius: '8px', border: '1px solid #D1D5DB', padding: '0 12px', fontSize: '14px', boxSizing: 'border-box' }}
          readOnly
        />
        <button style={{ height: '48px', width: '100%', borderRadius: '8px', background: '#059669', color: '#fff', fontSize: '14px', fontWeight: 600, border: 'none' }}>
          Submit
        </button>
      </div>
    </div>
  );
}
