const branches = [
  { name: 'Varuflow AB', flag: '🇸🇪', plan: 'Pro', active: true },
  { name: 'Varuflow Norge AS', flag: '🇳🇴', plan: 'Pro', active: false },
  { name: 'Varuflow Danmark ApS', flag: '🇩🇰', plan: 'Starter', active: false },
];

export function Trigger() {
  return (
    <div style={{ padding: '16px', background: '#0f1117', maxWidth: '280px' }}>
      <button type="button" style={{
        display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
        padding: '8px 12px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer',
      }}>
        <span style={{ fontSize: '16px' }}>🇸🇪</span>
        <span style={{ flex: 1, textAlign: 'left', fontSize: '13px', fontWeight: '500', color: '#f9fafb' }}>Varuflow AB</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2"><polyline points="6 9 12 15 18 9" /></svg>
      </button>
    </div>
  );
}

export function Dropdown() {
  return (
    <div style={{ padding: '16px', background: '#0f1117', maxWidth: '280px' }}>
      <button type="button" style={{
        display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
        padding: '8px 12px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer', marginBottom: '4px',
      }}>
        <span style={{ fontSize: '16px' }}>🇸🇪</span>
        <span style={{ flex: 1, textAlign: 'left', fontSize: '13px', fontWeight: '500', color: '#f9fafb' }}>Varuflow AB</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2"><polyline points="18 15 12 9 6 15" /></svg>
      </button>
      <div style={{
        background: '#1a1f2e', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.08)',
        overflow: 'hidden', boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
      }}>
        {branches.map(b => (
          <div key={b.name} style={{
            display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px',
            background: b.active ? 'rgba(255,255,255,0.06)' : 'transparent', cursor: 'pointer',
          }}>
            <span style={{ fontSize: '16px' }}>{b.flag}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '13px', fontWeight: '500', color: '#f9fafb' }}>{b.name}</div>
              <div style={{ fontSize: '11px', color: '#6b7280' }}>{b.plan}</div>
            </div>
            {b.active && <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>}
          </div>
        ))}
      </div>
    </div>
  );
}
