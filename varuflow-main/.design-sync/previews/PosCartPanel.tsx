/**
 * PosCartPanel reads all state from PosProvider context and uses framer-motion.
 * We render a faithful static reproduction showing a cart with 2 items, totals,
 * payment method selector, and Complete Sale button.
 */

export function CartWithItems() {
  const cartItems = [
    { id: 'p1', name: 'Oatly Havredryck 1L', unitPrice: 18.9, qty: 2, discountPct: 0 },
    { id: 'p2', name: 'Marabou Mjölkchoklad 200g', unitPrice: 29.9, qty: 1, discountPct: 10 },
  ];

  const subtotal = cartItems.reduce((s, it) => s + it.unitPrice * it.qty * (1 - it.discountPct / 100), 0);
  const vat = subtotal * 0.25;
  const total = subtotal + vat;
  const totalQty = cartItems.reduce((s, it) => s + it.qty, 0);

  return (
    <aside style={{
      display: 'flex', flexDirection: 'column', gap: '12px',
      borderRadius: '12px', border: '1px solid #e5e7eb', background: '#fff',
      padding: '16px', boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      width: '320px', fontFamily: 'system-ui, sans-serif'
    }}>
      <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', borderBottom: '1px solid #f3f4f6', paddingBottom: '8px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', margin: 0 }}>Kassa</h2>
        <span style={{ background: '#d1fae5', color: '#065f46', borderRadius: '9999px', padding: '2px 8px', fontSize: '12px', fontWeight: 500 }}>{totalQty}</span>
      </header>

      {/* Customer search */}
      <input placeholder="Search customer…" style={{ height: '40px', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 12px', fontSize: '14px', color: '#9ca3af' }} />

      {/* Cart items */}
      <ul style={{ flex: 1, listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {cartItems.map((it) => (
          <li key={it.id} style={{ background: '#f9fafb', borderRadius: '8px', padding: '8px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '8px', alignItems: 'center' }}>
              <div>
                <p style={{ fontSize: '14px', fontWeight: 500, color: '#111827', margin: '0 0 2px' }}>{it.name}</p>
                <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>
                  {it.unitPrice.toFixed(2)} × {it.qty}
                  {it.discountPct > 0 && <span style={{ marginLeft: '4px', color: '#d97706' }}>-{it.discountPct}%</span>}
                  {' '}= {(it.unitPrice * it.qty * (1 - it.discountPct / 100)).toFixed(2)} SEK
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <button style={{ width: '44px', height: '44px', borderRadius: '8px', background: '#fff', border: '1px solid #e5e7eb', fontSize: '20px', fontWeight: 700, color: '#374151', cursor: 'pointer' }}>−</button>
                <span style={{ minWidth: '20px', textAlign: 'center', fontWeight: 600, color: '#111827' }}>{it.qty}</span>
                <button style={{ width: '44px', height: '44px', borderRadius: '8px', background: '#fff', border: '1px solid #e5e7eb', fontSize: '20px', fontWeight: 700, color: '#374151', cursor: 'pointer' }}>+</button>
                <button style={{ width: '44px', height: '44px', borderRadius: '8px', color: '#dc2626', background: 'transparent', border: 'none', fontSize: '18px', cursor: 'pointer' }}>×</button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {/* Totals */}
      <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: '12px', fontSize: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6b7280' }}>
          <span>Subtotal</span><span style={{ fontVariantNumeric: 'tabular-nums' }}>{subtotal.toFixed(2)} SEK</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#6b7280' }}>
          <span>VAT (25%)</span><span style={{ fontVariantNumeric: 'tabular-nums' }}>{vat.toFixed(2)} SEK</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, fontSize: '16px', color: '#111827', borderTop: '1px solid #f3f4f6', paddingTop: '8px', marginTop: '2px' }}>
          <span>Total</span><span style={{ fontVariantNumeric: 'tabular-nums' }}>{total.toFixed(2)} SEK</span>
        </div>
      </div>

      {/* Payment methods */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        {[{ key: 'cash', emoji: '💵', label: 'Cash' }, { key: 'card', emoji: '💳', label: 'Card' }, { key: 'swish', emoji: '📱', label: 'Swish' }].map((m) => (
          <button key={m.key} style={{
            minHeight: '56px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            borderRadius: '8px', border: m.key === 'card' ? '2px solid #059669' : '1px solid #e5e7eb',
            background: m.key === 'card' ? '#059669' : '#fff', color: m.key === 'card' ? '#fff' : '#374151',
            fontSize: '13px', fontWeight: 500, cursor: 'pointer'
          }}>
            <span style={{ fontSize: '20px', marginBottom: '2px' }}>{m.emoji}</span>
            {m.label}
          </button>
        ))}
      </div>

      {/* Complete sale */}
      <button style={{
        marginTop: '8px', height: '56px', width: '100%', borderRadius: '12px',
        background: '#059669', border: 'none', color: '#fff', fontSize: '16px', fontWeight: 600,
        cursor: 'pointer', boxShadow: '0 4px 12px rgba(5,150,105,0.35)'
      }}>
        Complete sale
      </button>
    </aside>
  );
}

export function EmptyCart() {
  return (
    <aside style={{
      display: 'flex', flexDirection: 'column', gap: '12px',
      borderRadius: '12px', border: '1px solid #e5e7eb', background: '#fff',
      padding: '16px', width: '320px', fontFamily: 'system-ui, sans-serif'
    }}>
      <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', borderBottom: '1px solid #f3f4f6', paddingBottom: '8px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', margin: 0 }}>Kassa</h2>
        <span style={{ background: '#d1fae5', color: '#065f46', borderRadius: '9999px', padding: '2px 8px', fontSize: '12px', fontWeight: 500 }}>0</span>
      </header>
      <input placeholder="Search customer…" style={{ height: '40px', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 12px', fontSize: '14px', color: '#9ca3af' }} />
      <div style={{ flex: 1, padding: '24px 0', textAlign: 'center', fontSize: '14px', color: '#9ca3af' }}>Cart is empty</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        {['💵 Cash', '💳 Card', '📱 Swish'].map((m) => (
          <button key={m} style={{ minHeight: '56px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: '13px', cursor: 'pointer' }}>{m}</button>
        ))}
      </div>
      <button disabled style={{ height: '56px', borderRadius: '12px', background: '#d1d5db', border: 'none', color: '#fff', fontSize: '16px', fontWeight: 600, cursor: 'not-allowed' }}>
        Complete sale
      </button>
    </aside>
  );
}
