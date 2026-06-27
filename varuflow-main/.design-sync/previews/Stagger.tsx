/**
 * Stagger and StaggerItem use framer-motion useReducedMotion which may fail
 * in the preview bundle environment. Write a pure static reproduction showing
 * the layout that Stagger would produce (children stacked/gridded).
 */

export function BasicList() {
  const items = ['Dashboard overview', 'Sales analytics', 'Inventory report', 'Customer insights'];
  return (
    <div style={{ padding: '16px', maxWidth: '400px', fontFamily: 'system-ui, sans-serif', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <p style={{ fontSize: '11px', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Stagger — staggered list animation wrapper (static)</p>
      {items.map((item, i) => (
        <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px', padding: '14px 16px', fontSize: '14px', fontWeight: 500, color: '#111827', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          {item}
        </div>
      ))}
    </div>
  );
}

export function CardGrid() {
  const cards = [
    { title: 'Revenue', value: '248 400 kr', color: '#6366f1' },
    { title: 'Orders', value: '1 247', color: '#059669' },
    { title: 'Customers', value: '384', color: '#d97706' },
    { title: 'Returns', value: '23', color: '#dc2626' },
  ];
  return (
    <div style={{ padding: '16px', fontFamily: 'system-ui, sans-serif' }}>
      <p style={{ fontSize: '11px', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 12px' }}>Stagger — staggered grid animation wrapper (static)</p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        {cards.map((card, i) => (
          <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '16px', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#9ca3af', marginBottom: '4px' }}>{card.title}</div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
