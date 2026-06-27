const steps = [
  { label: 'Add your first product', done: true },
  { label: 'Add your first customer', done: true },
  { label: 'Create your first invoice', done: false },
  { label: 'Invite a team member', done: false },
  { label: 'Connect Fortnox', done: false },
  { label: 'Send your first invoice', done: false },
];

export function InProgress() {
  const pct = Math.round((steps.filter(s => s.done).length / steps.length) * 100);
  return (
    <div style={{ maxWidth: '380px', padding: '8px' }}>
      <div style={{
        background: '#fff', borderRadius: '16px',
        border: '1px solid #e5e7eb', overflow: 'hidden',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}>
        <div style={{ padding: '16px 20px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '600', color: '#111827', margin: 0 }}>
              Getting started
            </h3>
            <span style={{ fontSize: '12px', color: '#6b7280' }}>{pct}% done</span>
          </div>
          <div style={{ height: '4px', background: '#f3f4f6', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct}%`, background: '#2d6a4f', borderRadius: '2px' }} />
          </div>
        </div>
        <ul style={{ listStyle: 'none', margin: 0, padding: '0 12px 16px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {steps.map(s => (
            <li key={s.label} style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '8px', borderRadius: '8px',
            }}>
              {s.done ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2d6a4f" strokeWidth="2.5"><circle cx="12" cy="12" r="10" fill="#dcfce7" stroke="#2d6a4f" /><polyline points="20 6 9 17 4 12" stroke="#2d6a4f" /></svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="2"><circle cx="12" cy="12" r="10" /></svg>
              )}
              <span style={{
                fontSize: '13px', color: s.done ? '#9ca3af' : '#374151',
                textDecoration: s.done ? 'line-through' : 'none',
              }}>{s.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
