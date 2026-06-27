export function Banner() {
  return (
    <div style={{ maxWidth: '390px', padding: '8px', background: '#f9fafb' }}>
      <div style={{
        background: '#fff', borderRadius: '14px', padding: '16px 20px',
        border: '1px solid #e5e7eb', boxShadow: '0 2px 10px rgba(0,0,0,0.07)',
        display: 'flex', alignItems: 'center', gap: '14px',
      }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px', background: '#2563eb',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M12 8v8M8 12l4-4 4 4" /></svg>
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: '14px', fontWeight: '600', color: '#111827', margin: '0 0 2px' }}>
            Install Varuflow
          </p>
          <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>
            Add to home screen for quick access
          </p>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button type="button" style={{
            padding: '7px 14px', borderRadius: '8px', border: '1px solid #e5e7eb',
            background: '#fff', fontSize: '12px', color: '#6b7280', cursor: 'pointer',
          }}>Later</button>
          <button type="button" style={{
            padding: '7px 14px', borderRadius: '8px', border: 'none',
            background: '#2563eb', fontSize: '12px', color: '#fff', fontWeight: '600', cursor: 'pointer',
          }}>Install</button>
        </div>
      </div>
    </div>
  );
}
