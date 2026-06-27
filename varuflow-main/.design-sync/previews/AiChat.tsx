const messages = [
  { role: 'user', content: 'Which invoices are overdue and need follow-up?' },
  { role: 'assistant', content: 'You have 3 overdue invoices totalling 23 400 kr:\n\n• INV-2024-0138 — Eriksson & Partners · 8 500 kr · 18 days overdue\n• INV-2024-0141 — Björk AB · 9 200 kr · 12 days overdue\n• INV-2024-0143 — Lindström Bygg · 5 700 kr · 7 days overdue\n\nWould you like me to draft reminder emails for these customers?' },
  { role: 'user', content: 'Yes, draft the reminders.' },
];

const quickPrompts = [
  'What products are at stockout risk?',
  'Summarize my cash flow',
  'Top 5 customers by revenue',
];

export function OpenPanel() {
  return (
    <div style={{ padding: '16px', background: '#0f1117', maxWidth: '420px' }}>
      <div style={{
        background: '#1a1f2e', borderRadius: '16px', overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)',
          background: '#111827',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              width: '28px', height: '28px', borderRadius: '8px', background: '#2563eb',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><circle cx="12" cy="8" r="4" /><path d="M20 21a8 8 0 10-16 0" /></svg>
            </span>
            <span style={{ fontSize: '14px', fontWeight: '600', color: '#f9fafb' }}>Varuflow AI</span>
          </div>
          <button type="button" style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', padding: '4px' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '320px', overflowY: 'auto' }}>
          {messages.map((m, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              <div style={{
                maxWidth: '85%', padding: '10px 14px', borderRadius: m.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                background: m.role === 'user' ? '#2563eb' : 'rgba(255,255,255,0.06)',
                color: m.role === 'user' ? '#fff' : '#d1d5db',
                fontSize: '13px', lineHeight: '1.5', whiteSpace: 'pre-wrap',
              }}>
                {m.content}
              </div>
            </div>
          ))}
        </div>
        <div style={{ padding: '8px 16px 8px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
            {quickPrompts.map(p => (
              <button key={p} type="button" style={{
                fontSize: '11px', color: '#9ca3af', background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)', borderRadius: '100px',
                padding: '4px 10px', cursor: 'pointer',
              }}>{p}</button>
            ))}
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            background: 'rgba(255,255,255,0.06)', borderRadius: '10px', padding: '10px 12px',
            border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <input type="text" placeholder="Ask anything about your business…" style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              color: '#d1d5db', fontSize: '13px',
            }} />
            <button type="button" style={{
              width: '28px', height: '28px', borderRadius: '6px', background: '#2563eb',
              border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
