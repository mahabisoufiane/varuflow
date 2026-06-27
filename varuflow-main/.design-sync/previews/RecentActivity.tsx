const events = [
  { label: 'Invoice INV-2024-0148 created', sub: '14 250 kr · Eriksson & Partners', time: '2 min ago', color: '#10b981', dot: '📄' },
  { label: 'Product "Trådlös mus" updated', sub: 'Stock: 12 → 8', time: '18 min ago', color: '#6366f1', dot: '📦' },
  { label: 'New customer registered', sub: 'Björk Bygg AB', time: '1h ago', color: '#f59e0b', dot: '👤' },
  { label: 'Payment received', sub: 'INV-2024-0141 · 9 200 kr', time: '3h ago', color: '#2563eb', dot: '💳' },
  { label: 'Invoice sent', sub: 'INV-2024-0147 · Anna Lindström', time: '5h ago', color: '#10b981', dot: '📨' },
];

export function Default() {
  return (
    <div style={{ maxWidth: '420px', padding: '4px' }}>
      <div style={{ background: '#fff', borderRadius: '14px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid #f3f4f6' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '600', color: '#111827', margin: 0 }}>Recent activity</h3>
        </div>
        <ul style={{ listStyle: 'none', margin: 0, padding: '4px 0' }}>
          {events.map((e, i) => (
            <li key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: '12px',
              padding: '10px 16px', borderBottom: i < events.length - 1 ? '1px solid #f9fafb' : 'none',
            }}>
              <span style={{ fontSize: '16px', marginTop: '1px', flexShrink: 0 }}>{e.dot}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: '13px', fontWeight: '500', color: '#111827', margin: '0 0 2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.label}</p>
                <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>{e.sub}</p>
              </div>
              <span style={{ fontSize: '11px', color: '#9ca3af', flexShrink: 0 }}>{e.time}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
