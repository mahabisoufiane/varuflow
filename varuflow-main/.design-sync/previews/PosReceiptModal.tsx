/**
 * PosReceiptModal relies on usePos() context. Static reproduction of the
 * receipt modal in "shown" state after a successful sale.
 */

export function ReceiptModal() {
  return (
    <div style={{ position: 'relative', minHeight: '360px', background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', borderRadius: '12px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ width: '100%', maxWidth: '420px', background: '#fff', borderRadius: '16px', padding: '24px', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', margin: 0 }}>#POS-2024-0841</h3>
          <span style={{ fontSize: '18px', fontWeight: 700, color: '#059669' }}>184.75 SEK</span>
        </div>

        <div style={{ background: '#d1fae5', borderRadius: '8px', padding: '10px 12px', marginBottom: '16px', fontSize: '14px', color: '#065f46' }}>
          Change due: <strong>15.25 SEK</strong>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <button style={{
            minHeight: '72px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            borderRadius: '12px', border: '1px solid #e5e7eb', background: '#fff',
            fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#374151', gap: '4px'
          }}>
            <span style={{ fontSize: '22px' }}>🖨️</span>
            Print receipt
          </button>
          <button style={{
            minHeight: '72px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            borderRadius: '12px', border: '1px solid #e5e7eb', background: '#fff',
            fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#374151', gap: '4px'
          }}>
            <span style={{ fontSize: '22px' }}>📧</span>
            Email receipt
          </button>
          <button style={{
            minHeight: '72px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            borderRadius: '12px', border: '1px solid #fecaca', background: '#fff',
            fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#dc2626', gap: '4px'
          }}>
            <span style={{ fontSize: '22px' }}>↩️</span>
            Refund
          </button>
          <button style={{
            minHeight: '72px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            borderRadius: '12px', border: 'none', background: '#059669',
            fontSize: '14px', fontWeight: 600, cursor: 'pointer', color: '#fff', gap: '4px'
          }}>
            <span style={{ fontSize: '22px' }}>➡️</span>
            New sale
          </button>
        </div>
      </div>
    </div>
  );
}
