import BarcodeScanner from 'varuflow-ui';

/**
 * BarcodeScanner is a full-screen camera overlay component that requires
 * getUserMedia. In a static preview environment there is no camera stream,
 * so we render the ScannerShell in its "loading" state to show the UI chrome.
 * The component renders a modal overlay; we wrap it in a relative container
 * with fixed height so it doesn't expand to viewport.
 */
export function CameraOverlayUI() {
  return (
    <div style={{ position: 'relative', width: '380px', height: '340px', overflow: 'hidden', borderRadius: '16px', border: '1px solid #e5e7eb' }}>
      <div style={{ position: 'absolute', inset: 0, background: '#000', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: 'rgba(0,0,0,0.6)' }}>
          <p style={{ fontSize: '14px', fontWeight: 500, color: '#fff', margin: 0 }}>Point camera at barcode</p>
          <button style={{ borderRadius: '50%', width: 28, height: 28, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
        </div>

        {/* Camera area with viewfinder */}
        <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#111' }}>
          {/* Dim overlay */}
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }} />
          {/* Viewfinder box */}
          <div style={{ position: 'relative', width: '224px', height: '128px', zIndex: 2 }}>
            {/* Corner brackets */}
            <div style={{ position: 'absolute', top: 0, left: 0, width: 24, height: 24, borderTop: '2px solid #34d399', borderLeft: '2px solid #34d399' }} />
            <div style={{ position: 'absolute', top: 0, right: 0, width: 24, height: 24, borderTop: '2px solid #34d399', borderRight: '2px solid #34d399' }} />
            <div style={{ position: 'absolute', bottom: 0, left: 0, width: 24, height: 24, borderBottom: '2px solid #34d399', borderLeft: '2px solid #34d399' }} />
            <div style={{ position: 'absolute', bottom: 0, right: 0, width: 24, height: 24, borderBottom: '2px solid #34d399', borderRight: '2px solid #34d399' }} />
            {/* Scan line */}
            <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 2, background: '#34d399', boxShadow: '0 0 8px 2px rgba(52,211,153,0.5)', borderRadius: 2 }} />
          </div>
        </div>

        <p style={{ textAlign: 'center', fontSize: '12px', color: 'rgba(255,255,255,0.5)', padding: '12px 16px', background: '#000', margin: 0 }}>
          ESC or tap background to close
        </p>
      </div>
    </div>
  );
}
