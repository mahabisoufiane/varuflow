export function Warning() {
  return (
    <div style={{ position: 'relative', minHeight: '320px', background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{
        background: '#1a1f2e', borderRadius: '16px', padding: '28px 24px',
        border: '1px solid rgba(255,255,255,0.10)', maxWidth: '340px', width: '100%',
        textAlign: 'center', boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
      }}>
        <div style={{
          width: '48px', height: '48px', borderRadius: '50%', background: '#fef9c3',
          display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px',
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" strokeWidth="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
        </div>
        <h3 style={{ fontSize: '17px', fontWeight: '700', color: '#f9fafb', margin: '0 0 8px' }}>
          Session expiring soon
        </h3>
        <p style={{ fontSize: '14px', color: '#9ca3af', margin: '0 0 20px', lineHeight: '1.5' }}>
          Your session will expire in{' '}
          <span aria-live="polite" style={{ fontWeight: '700', color: '#fbbf24', fontSize: '16px' }}>30</span>
          {' '}seconds due to inactivity.
        </p>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button type="button" style={{
            flex: 1, padding: '10px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.10)',
            background: 'transparent', color: '#9ca3af', fontSize: '14px', cursor: 'pointer',
          }}>
            Log out now
          </button>
          <button type="button" style={{
            flex: 1, padding: '10px', borderRadius: '10px', border: 'none',
            background: '#2563eb', color: '#fff', fontSize: '14px', fontWeight: '600', cursor: 'pointer',
          }}>
            Stay connected
          </button>
        </div>
      </div>
    </div>
  );
}
