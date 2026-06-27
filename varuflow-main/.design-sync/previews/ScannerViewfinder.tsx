import { ScannerViewfinder } from 'varuflow-ui';

export function ActiveScanning() {
  return (
    <div style={{ background: '#111', borderRadius: '12px', overflow: 'hidden', width: '380px' }}>
      <div style={{ padding: '10px 16px' }}>
        <p style={{ color: '#fff', fontSize: '14px', fontWeight: 500, margin: 0 }}>Point camera at barcode</p>
      </div>
      <div style={{ position: 'relative', height: '240px', background: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Simulated dark camera bg */}
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%)' }} />
        {/* Dim overlay */}
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }} />
        <ScannerViewfinder scanning={true} innerClassName="w-56 h-32" />
      </div>
      <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px', textAlign: 'center', padding: '10px 16px', margin: 0, background: '#000' }}>
        ESC or tap background to close
      </p>
    </div>
  );
}

export function CustomColor() {
  return (
    <div style={{ background: '#0f172a', borderRadius: '12px', overflow: 'hidden', width: '380px', padding: '16px' }}>
      <div style={{ position: 'relative', height: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <ScannerViewfinder scanning={true} color="#f59e0b" innerClassName="w-64 h-36" />
      </div>
      <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '12px', textAlign: 'center', margin: '8px 0 0' }}>Amber variant</p>
    </div>
  );
}

export function NotScanning() {
  return (
    <div style={{ padding: '16px', background: '#f9fafb', borderRadius: '12px' }}>
      <p style={{ fontSize: '14px', color: '#6b7280', margin: 0 }}>
        ScannerViewfinder with <code>scanning=false</code> renders null — no visible output.
      </p>
    </div>
  );
}
