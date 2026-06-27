const bankBtnStyle: React.CSSProperties = {
  display: 'flex', width: '100%', height: '44px', alignItems: 'center',
  justifyContent: 'center', gap: '12px', borderRadius: '12px',
  border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.06)',
  fontSize: '14px', fontWeight: '500', color: '#f9fafb', cursor: 'pointer',
  backgroundColor: '#1c2333',
};
const bankBadge: React.CSSProperties = {
  display: 'inline-flex', height: '16px', width: '16px', alignItems: 'center',
  justifyContent: 'center', borderRadius: '4px', background: '#193E8F',
  fontSize: '10px', fontWeight: '700', color: '#fff',
};

export function Default() {
  return (
    <div style={{ padding: '24px', background: '#0f1117', maxWidth: '320px' }}>
      <button type="button" style={bankBtnStyle}>
        <span style={bankBadge}>B</span>
        Log in with BankID
      </button>
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ padding: '24px', background: '#0f1117', maxWidth: '320px' }}>
      <button type="button" disabled style={{ ...bankBtnStyle, opacity: 0.4, cursor: 'not-allowed' }}>
        <span style={bankBadge}>B</span>
        Log in with BankID
      </button>
    </div>
  );
}

export function QrModal() {
  return (
    <div style={{ padding: '24px', background: '#0f1117', maxWidth: '360px' }}>
      <div style={{
        background: '#111827', borderRadius: '16px', padding: '24px',
        border: '1px solid rgba(255,255,255,0.10)', textAlign: 'center', color: '#f9fafb',
      }}>
        <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px', margin: '0 0 8px' }}>
          Log in with BankID
        </h3>
        <p style={{ fontSize: '14px', color: '#9ca3af', margin: '0 0 16px' }}>
          Scan the QR code with your BankID app
        </p>
        <div style={{
          background: '#fff', borderRadius: '12px', padding: '16px',
          display: 'inline-block', marginBottom: '16px',
        }}>
          <div style={{ width: '160px', height: '160px', background: '#e5e7eb' }} />
        </div>
        <div>
          <a style={{ fontSize: '14px', fontWeight: '500', color: '#193E8F', cursor: 'pointer' }}>
            Open on this device →
          </a>
        </div>
      </div>
    </div>
  );
}
