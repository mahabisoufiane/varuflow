/**
 * PosSessionControls uses usePos() context and api. Static reproduction of
 * both states: no session (open prompt) and session open (close button + Z-report modal).
 */

export function OpenSessionPrompt() {
  return (
    <div style={{ padding: '16px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <input
          type="number"
          placeholder="Opening float (SEK)"
          defaultValue={500}
          style={{ height: '44px', width: '144px', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 12px', fontSize: '14px' }}
        />
        <button style={{ height: '44px', borderRadius: '8px', background: '#059669', color: '#fff', border: 'none', padding: '0 16px', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>
          Open session
        </button>
      </div>
    </div>
  );
}

export function SessionOpen() {
  return (
    <div style={{ padding: '16px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#d1fae5', borderRadius: '8px', padding: '8px 12px', fontSize: '13px', color: '#065f46', fontWeight: 500 }}>
          <span style={{ width: '8px', height: '8px', background: '#059669', borderRadius: '50%', display: 'inline-block' }} />
          Session open — 09:03
        </div>
        <button style={{ height: '44px', borderRadius: '8px', border: '1px solid #d1d5db', background: '#fff', padding: '0 16px', fontSize: '14px', fontWeight: 500, cursor: 'pointer', color: '#374151' }}>
          Close session
        </button>
      </div>
    </div>
  );
}

export function ZReportModal() {
  return (
    <div style={{ position: 'relative', minHeight: '460px', background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', borderRadius: '12px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ width: '100%', maxWidth: '480px', background: '#fff', borderRadius: '16px', padding: '24px', boxShadow: '0 20px 60px rgba(0,0,0,0.25)' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', margin: '0 0 16px' }}>Z-report — End of Day</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '14px', color: '#374151', marginBottom: '16px' }}>
          {[
            ['Sales', '47'],
            ['Total revenue', '8 432.50 SEK'],
            ['Cash', '2 140.00'],
            ['Card', '5 892.50'],
            ['Swish', '400.00'],
            ['Opening float', '500.00'],
            ['Expected cash', '2 640.00'],
          ].map(([label, value]) => (
            <>
              <div key={label} style={{ color: '#6b7280' }}>{label}</div>
              <div key={value} style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
            </>
          ))}
        </div>
        <label style={{ display: 'block', fontSize: '14px', color: '#6b7280', marginBottom: '4px' }}>Counted cash</label>
        <input type="number" defaultValue={2640} style={{ height: '44px', width: '100%', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 12px', fontSize: '14px', marginBottom: '8px', boxSizing: 'border-box' }} />
        <p style={{ fontSize: '14px', color: '#059669', marginBottom: '12px' }}>Cash variance: 0.00 SEK</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <button style={{ height: '44px', borderRadius: '8px', border: '1px solid #d1d5db', background: '#fff', padding: '0 16px', fontSize: '14px', color: '#374151', cursor: 'pointer' }}>Download PDF</button>
          <button style={{ height: '44px', flex: 1, borderRadius: '8px', background: '#059669', border: 'none', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>Confirm close</button>
          <button style={{ height: '44px', borderRadius: '8px', background: 'transparent', border: 'none', color: '#6b7280', cursor: 'pointer', padding: '0 12px' }}>✕</button>
        </div>
      </div>
    </div>
  );
}
