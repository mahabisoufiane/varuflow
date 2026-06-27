export function Fab() {
  return (
    <div style={{ padding: '40px', display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end', minHeight: '120px' }}>
      <button type="button" style={{
        width: '56px', height: '56px', borderRadius: '50%', background: '#2d6a4f',
        color: '#fff', border: 'none', display: 'flex', alignItems: 'center',
        justifyContent: 'center', boxShadow: '0 4px 14px rgba(45,106,79,0.4)', cursor: 'pointer',
      }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>
    </div>
  );
}

export function FabWithBadge() {
  return (
    <div style={{ padding: '40px', display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end', minHeight: '120px' }}>
      <div style={{ position: 'relative' }}>
        <button type="button" style={{
          width: '56px', height: '56px', borderRadius: '50%', background: '#2d6a4f',
          color: '#fff', border: 'none', display: 'flex', alignItems: 'center',
          justifyContent: 'center', boxShadow: '0 4px 14px rgba(45,106,79,0.4)', cursor: 'pointer',
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
        <span style={{
          position: 'absolute', top: '-4px', right: '-4px', minWidth: '20px', minHeight: '20px',
          borderRadius: '10px', background: '#ef4444', color: '#fff', fontSize: '11px',
          fontWeight: '600', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px',
        }}>3</span>
      </div>
    </div>
  );
}

export function OpenSheet() {
  const actions = ['New Invoice', 'Add Product', 'New Customer', 'Stock Movement', 'New Booking'];
  return (
    <div style={{ maxWidth: '375px' }}>
      <div style={{
        background: '#fff', borderRadius: '16px 16px 0 0', paddingBottom: '24px',
        boxShadow: '0 -8px 30px rgba(0,0,0,0.15)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
          <span style={{ width: '32px', height: '4px', borderRadius: '2px', background: '#d1d5db' }} />
        </div>
        <h3 style={{ textAlign: 'center', fontSize: '15px', fontWeight: '600', color: '#111827', margin: '0 0 16px' }}>
          Quick Actions
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', padding: '0 16px' }}>
          {actions.map(a => (
            <button key={a} type="button" style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
              padding: '14px 8px', borderRadius: '12px', background: '#f9fafb',
              border: '1px solid #f3f4f6', cursor: 'pointer',
            }}>
              <span style={{
                width: '36px', height: '36px', borderRadius: '10px', background: '#e0f2f7',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0891b2" strokeWidth="2" strokeLinecap="round">
                  <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </span>
              <span style={{ fontSize: '11px', fontWeight: '500', color: '#374151', textAlign: 'center' }}>{a}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
