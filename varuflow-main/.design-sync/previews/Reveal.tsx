export function FadeIn() {
  return (
    <div style={{ padding: '32px', background: '#f5f5f5', maxWidth: '480px' }}>
      <div style={{ padding: '24px', background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
        <h2 style={{ margin: '0 0 8px', fontSize: '18px', fontWeight: 600, color: '#111827' }}>
          Varuflow Business OS
        </h2>
        <p style={{ margin: 0, color: '#6b7280', lineHeight: '1.6' }}>
          This block fades and rises into view as it scrolls into the viewport. The Reveal component wraps any content block with a smooth entrance animation.
        </p>
      </div>
    </div>
  );
}

export function StaggeredList() {
  const items = [
    { label: 'Add your first product', bg: '#e0f2fe', color: '#0369a1' },
    { label: 'Create a customer record', bg: '#dcfce7', color: '#15803d' },
    { label: 'Send your first invoice', bg: '#fef3c7', color: '#b45309' },
  ];
  return (
    <div style={{ padding: '32px', background: '#f5f5f5', maxWidth: '480px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {items.map((item, i) => (
        <div key={i} style={{
          padding: '16px 20px', background: item.bg, borderRadius: '10px',
          fontSize: '14px', fontWeight: '500', color: item.color,
          display: 'flex', alignItems: 'center', gap: '10px',
        }}>
          <span style={{
            width: '22px', height: '22px', borderRadius: '50%', background: item.color + '20',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '12px', fontWeight: '700', color: item.color, flexShrink: 0,
          }}>{i + 1}</span>
          {item.label}
          <span style={{ marginLeft: 'auto', fontSize: '12px', color: item.color + '80' }}>
            delay: {i * 100}ms
          </span>
        </div>
      ))}
    </div>
  );
}
