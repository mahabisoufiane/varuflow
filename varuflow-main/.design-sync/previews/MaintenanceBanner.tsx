export function Active() {
  return (
    <div style={{ background: '#fef2cd', borderBottom: '1px solid #fde68a', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#b45309" strokeWidth="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
      <p style={{ fontSize: '13px', color: '#92400e', margin: 0, flex: 1 }}>
        <strong>Scheduled maintenance</strong> — Varuflow will be in read-only mode on Saturday 28 June 02:00–04:00 CET.
      </p>
      <button type="button" style={{ background: 'none', border: 'none', color: '#92400e', cursor: 'pointer', padding: '2px' }}>✕</button>
    </div>
  );
}

export function ReadOnly() {
  return (
    <div style={{ background: '#fee2e2', borderBottom: '1px solid #fecaca', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
      <p style={{ fontSize: '13px', color: '#7f1d1d', margin: 0 }}>
        <strong>Read-only mode</strong> — System is undergoing maintenance. No changes can be saved right now.
      </p>
    </div>
  );
}
