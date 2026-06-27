export function Banner() {
  return (
    <div style={{ background: '#f9fafb', padding: '24px' }}>
      <div style={{
        background: '#fff', borderRadius: '14px', padding: '20px 24px',
        border: '1px solid #e5e7eb', boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
        display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '16px',
      }}>
        <span style={{ fontSize: '24px' }}>🍪</span>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <p style={{ fontSize: '14px', fontWeight: '600', color: '#111827', margin: '0 0 4px' }}>
            Cookie preferences
          </p>
          <p style={{ fontSize: '13px', color: '#6b7280', margin: 0, lineHeight: '1.5' }}>
            We use cookies to improve your experience. You can choose which cookies to allow.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <button type="button" style={{
            padding: '8px 16px', borderRadius: '8px', border: '1px solid #e5e7eb',
            background: '#fff', fontSize: '13px', color: '#374151', cursor: 'pointer',
          }}>Preferences</button>
          <button type="button" style={{
            padding: '8px 16px', borderRadius: '8px', border: 'none',
            background: '#2563eb', fontSize: '13px', color: '#fff', fontWeight: '600', cursor: 'pointer',
          }}>Accept all</button>
        </div>
      </div>
    </div>
  );
}
