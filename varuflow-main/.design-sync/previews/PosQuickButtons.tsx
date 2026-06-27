/**
 * PosQuickButtons fetches from API on load. Static reproduction of the
 * quick-button bar in loaded state.
 */

const quickButtons = [
  { id: 'qb1', label: 'Oatly 1L', color: '#059669', quantity: 1 },
  { id: 'qb2', label: 'Mjölk 3%', color: '#6366f1', quantity: 1 },
  { id: 'qb3', label: 'Kaffe 500g', color: '#d97706', quantity: 1 },
  { id: 'qb4', label: 'Choklad ×2', color: '#dc2626', quantity: 2 },
  { id: 'qb5', label: 'Ketchup', color: '#7c3aed', quantity: 1 },
];

export function QuickButtonBar() {
  return (
    <div style={{ padding: '16px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
        {quickButtons.map((btn) => (
          <button
            key={btn.id}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              height: '48px', flexShrink: 0, borderRadius: '12px',
              border: `2px solid ${btn.color}`, background: '#fff',
              padding: '0 12px', fontSize: '14px', fontWeight: 600,
              color: '#111827', cursor: 'pointer'
            }}
          >
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: btn.color, display: 'inline-block' }} />
            {btn.label}
            {btn.quantity > 1 && (
              <span style={{ background: '#f3f4f6', color: '#6b7280', borderRadius: '4px', padding: '0 4px', fontSize: '12px' }}>
                ×{btn.quantity}
              </span>
            )}
          </button>
        ))}
        {/* Manage button */}
        <button style={{
          display: 'flex', alignItems: 'center', gap: '4px', height: '48px', flexShrink: 0,
          borderRadius: '12px', border: '1px dashed #d1d5db', background: '#fff',
          padding: '0 12px', fontSize: '14px', color: '#9ca3af', cursor: 'pointer'
        }}>
          ⚙
        </button>
      </div>
    </div>
  );
}

export function EmptyState() {
  return (
    <div style={{ padding: '16px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button style={{
          display: 'flex', alignItems: 'center', gap: '4px', height: '48px',
          borderRadius: '12px', border: '1px dashed #d1d5db', background: '#fff',
          padding: '0 12px', fontSize: '14px', color: '#9ca3af', cursor: 'pointer'
        }}>
          ⚙ Add quick button
        </button>
      </div>
      <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '8px' }}>
        No quick buttons configured. Add frequently sold items for one-tap checkout.
      </p>
    </div>
  );
}
