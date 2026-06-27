const aiCards = [
  { emoji: '📦', title: 'Low Stock Alert', body: '3 products below reorder threshold. Reorder to avoid stockouts this week.', action: 'View products' },
  { emoji: '💰', title: 'Revenue up 12%', body: 'Sales increased vs last month. Top performer: Trådlös mus (48 units).', action: 'See report' },
  { emoji: '⚠️', title: '2 Overdue Invoices', body: 'Invoices totalling 14 200 kr are 14+ days past due. Send reminders.', action: 'Follow up' },
];

export function Default() {
  return (
    <div style={{ maxWidth: '390px', padding: '16px', background: '#f9fafb' }}>
      <div style={{ display: 'flex', gap: '12px', overflowX: 'hidden' }}>
        {aiCards.map((c, i) => (
          <div key={i} style={{
            minWidth: '260px', background: '#fff', borderRadius: '14px',
            padding: '16px', border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>{c.emoji}</div>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#111827', margin: '0 0 6px' }}>{c.title}</h4>
            <p style={{ fontSize: '12px', color: '#6b7280', margin: '0 0 12px', lineHeight: '1.5' }}>{c.body}</p>
            <button type="button" style={{
              fontSize: '12px', fontWeight: '600', color: '#2563eb', background: '#eff6ff',
              border: '1px solid #bfdbfe', borderRadius: '8px', padding: '6px 12px', cursor: 'pointer',
            }}>{c.action} →</button>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '6px', marginTop: '12px' }}>
        {aiCards.map((_, i) => (
          <span key={i} style={{
            width: i === 0 ? '16px' : '6px', height: '6px', borderRadius: '3px',
            background: i === 0 ? '#2563eb' : '#d1d5db',
          }} />
        ))}
      </div>
    </div>
  );
}

export function Empty() {
  return (
    <div style={{ maxWidth: '390px', padding: '16px', background: '#f9fafb' }}>
      <div style={{
        background: '#fff', borderRadius: '14px', padding: '32px 24px',
        border: '1px solid #e5e7eb', textAlign: 'center',
      }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>✨</div>
        <p style={{ fontSize: '14px', color: '#6b7280', margin: 0 }}>
          No AI suggestions right now — everything looks good!
        </p>
      </div>
    </div>
  );
}
