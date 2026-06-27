/**
 * BarcodeInput depends on react-zxing (WASM camera) and useBarcodeListener.
 * We render a static faithful reproduction of the input UI for all three states.
 */

function EANBadge({ format, valid }: { format: string; valid: boolean }) {
  return (
    <span style={{
      position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)',
      borderRadius: '4px', padding: '2px 6px', fontSize: '10px', fontWeight: 700,
      background: valid ? '#d1fae5' : '#fef3c7',
      color: valid ? '#065f46' : '#92400e',
      pointerEvents: 'none'
    }}>
      {format} {valid ? '✓' : '⚠'}
    </span>
  );
}

export function WithEAN13() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px', fontFamily: 'system-ui, sans-serif' }}>
      <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#6b7280', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Barcode / EAN
      </label>
      <div style={{ display: 'flex', gap: '1px', marginBottom: '6px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            defaultValue="7310865085313"
            style={{ display: 'block', height: '40px', width: '100%', borderRadius: '6px 0 0 6px', border: '1px solid #10b981', padding: '0 80px 0 12px', fontFamily: 'monospace', fontSize: '14px', outline: 'none', boxSizing: 'border-box' }}
          />
          <EANBadge format="EAN-13" valid={true} />
        </div>
        <button style={{ width: '40px', height: '40px', border: '1px solid #d1d5db', borderLeft: 'none', background: '#fff', fontSize: '18px', cursor: 'pointer' }}>📷</button>
        <button style={{ width: '40px', height: '40px', border: '1px solid #d1d5db', borderLeft: 'none', borderRadius: '0 6px 6px 0', background: '#fff', color: '#9ca3af', fontSize: '14px', cursor: 'pointer' }}>✕</button>
      </div>
      <p style={{ fontSize: '11px', color: '#9ca3af', margin: 0, display: 'flex', alignItems: 'center', gap: '4px' }}>
        🔫 USB / Bluetooth scanner detected automatically when this field is focused
      </p>
    </div>
  );
}

export function Empty() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px', fontFamily: 'system-ui, sans-serif' }}>
      <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#6b7280', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Barcode / EAN — empty (shows Generate button)
      </label>
      <div style={{ display: 'flex', gap: '1px', marginBottom: '6px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            placeholder="7310865085313"
            style={{ display: 'block', height: '40px', width: '100%', borderRadius: '6px 0 0 6px', border: '1px solid #d1d5db', padding: '0 12px', fontFamily: 'monospace', fontSize: '14px', color: '#9ca3af', boxSizing: 'border-box' }}
          />
        </div>
        <button style={{ width: '40px', height: '40px', border: '1px solid #d1d5db', borderLeft: 'none', background: '#fff', fontSize: '18px', cursor: 'pointer' }}>📷</button>
        <button style={{ height: '40px', border: '1px dashed #d1d5db', borderLeft: 'none', borderRadius: '0 6px 6px 0', background: '#fff', padding: '0 10px', color: '#9ca3af', fontSize: '12px', fontWeight: 500, cursor: 'pointer' }}>
          Generate
        </button>
      </div>
      <p style={{ fontSize: '11px', color: '#9ca3af', margin: 0 }}>
        🔫 USB / Bluetooth scanner detected automatically when this field is focused
      </p>
    </div>
  );
}

export function WithCode128() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px', fontFamily: 'system-ui, sans-serif' }}>
      <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#6b7280', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Barcode — Code128 / alphanumeric
      </label>
      <div style={{ display: 'flex', gap: '1px', marginBottom: '6px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            defaultValue="VARUFLOW-SKU-2024"
            style={{ display: 'block', height: '40px', width: '100%', borderRadius: '6px 0 0 6px', border: '1px solid #d1d5db', padding: '0 110px 0 12px', fontFamily: 'monospace', fontSize: '14px', boxSizing: 'border-box' }}
          />
          <EANBadge format="Code128 / QR" valid={false} />
        </div>
        <button style={{ width: '40px', height: '40px', border: '1px solid #d1d5db', borderLeft: 'none', background: '#fff', fontSize: '18px', cursor: 'pointer' }}>📷</button>
        <button style={{ width: '40px', height: '40px', border: '1px solid #d1d5db', borderLeft: 'none', borderRadius: '0 6px 6px 0', background: '#fff', color: '#9ca3af', fontSize: '14px', cursor: 'pointer' }}>✕</button>
      </div>
      <p style={{ fontSize: '11px', color: '#9ca3af', margin: 0 }}>
        🔫 USB / Bluetooth scanner detected automatically when this field is focused
      </p>
    </div>
  );
}
