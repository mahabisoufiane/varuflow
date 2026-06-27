import { StaggerItem } from 'varuflow-ui';

/**
 * StaggerItem is a framer-motion wrapper — without a parent Stagger providing
 * the animation context the variants don't animate, but the component still
 * renders its children. We show it with realistic card content.
 */

export function SingleCard() {
  return (
    <div style={{ padding: '16px', maxWidth: '360px', fontFamily: 'system-ui, sans-serif' }}>
      <StaggerItem>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: '0 0 6px' }}>Q2 2026 Revenue</h3>
          <p style={{ fontSize: '28px', fontWeight: 700, color: '#6366f1', margin: '0 0 8px', fontVariantNumeric: 'tabular-nums' }}>248 400 kr</p>
          <p style={{ fontSize: '13px', color: '#059669', margin: 0 }}>↑ +12.4% vs Q1</p>
        </div>
      </StaggerItem>
    </div>
  );
}

export function MultipleItems() {
  const rows = [
    { product: 'Oatly Havredryck 1L', qty: 240, revenue: '4 536 kr' },
    { product: 'Marabou Mjölkchoklad', qty: 180, revenue: '5 382 kr' },
    { product: 'Gevalia Kaffe 500g', qty: 95, revenue: '6 555 kr' },
  ];
  return (
    <div style={{ padding: '16px', maxWidth: '500px', display: 'flex', flexDirection: 'column', gap: '8px', fontFamily: 'system-ui, sans-serif' }}>
      {rows.map((r, i) => (
        <StaggerItem key={i}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px', padding: '12px 16px' }}>
            <div>
              <p style={{ fontSize: '14px', fontWeight: 500, color: '#111827', margin: '0 0 2px' }}>{r.product}</p>
              <p style={{ fontSize: '12px', color: '#9ca3af', margin: 0 }}>Qty sold: {r.qty}</p>
            </div>
            <span style={{ fontSize: '15px', fontWeight: 600, color: '#059669' }}>{r.revenue}</span>
          </div>
        </StaggerItem>
      ))}
    </div>
  );
}
