const mockCards = [
  {
    type: 'ALERT', priority: 'HIGH',
    title: 'Low stock on 4 products',
    insight: 'Trådlös mus, USB-C Hub, and 2 others are at or below reorder threshold.',
    action: 'Reorder now to avoid stockouts before the weekend.',
    impact: 'Prevent ~15 000 kr in lost sales',
    color: '#ef4444', glow: 'rgba(239,68,68,0.08)',
  },
  {
    type: 'SUGGESTION', priority: 'MEDIUM',
    title: 'Follow up on 3 overdue invoices',
    insight: 'Invoices totalling 23 400 kr are 14+ days past due.',
    action: 'Send automated payment reminders via email.',
    impact: 'Recover ~23 400 kr',
    color: '#f59e0b', glow: 'rgba(245,158,11,0.08)',
  },
  {
    type: 'WORKFLOW', priority: 'LOW',
    title: 'Pricing opportunity detected',
    insight: '8 products priced below market average by 12–18%.',
    action: 'Review and adjust pricing for maximum margin.',
    impact: 'Increase margin by ~8 200 kr/month',
    color: '#6366f1', glow: 'rgba(99,102,241,0.08)',
  },
];

export function Default() {
  return (
    <div style={{ padding: '16px', background: '#0f1117', minWidth: '340px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <h2 style={{ color: '#f9fafb', fontSize: '15px', fontWeight: '600', margin: 0 }}>AI Action Cards</h2>
        <span style={{ fontSize: '11px', color: '#6b7280' }}>3 items</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {mockCards.map(c => (
          <div key={c.title} style={{
            border: `1px solid ${c.color}30`, borderRadius: '12px', padding: '16px',
            background: c.glow,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: '600', color: c.color, background: c.color + '20', padding: '2px 8px', borderRadius: '4px', border: `1px solid ${c.color}30` }}>{c.type}</span>
              <span style={{ fontSize: '11px', color: '#6b7280' }}>{c.priority}</span>
            </div>
            <p style={{ fontSize: '14px', fontWeight: '600', color: '#f9fafb', margin: '0 0 4px' }}>{c.title}</p>
            <p style={{ fontSize: '12px', color: '#9ca3af', margin: '0 0 8px', lineHeight: '1.5' }}>{c.insight}</p>
            <p style={{ fontSize: '12px', color: '#d1d5db', margin: '0 0 12px' }}>{c.action}</p>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', color: '#6b7280' }}>Impact: {c.impact}</span>
              <button type="button" style={{
                fontSize: '12px', fontWeight: '600', color: '#fff', background: c.color,
                border: 'none', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer',
              }}>Execute</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
