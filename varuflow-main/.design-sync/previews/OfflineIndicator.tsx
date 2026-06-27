// OfflineIndicator reads navigator.onLine and a real IndexedDB queue.
// In a preview sandbox these browser APIs are mocked/unavailable.
// We render the visible pill directly as a static replica so the
// visual design is captured without triggering the live hooks.

export function Default() {
  return (
    <div style={{ position: 'relative', height: '80px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div
        role="status"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          borderRadius: '9999px',
          border: '1px solid #FCD34D',
          background: '#FFFBEB',
          padding: '8px 16px',
          fontSize: '12px',
          fontWeight: 500,
          color: '#78350F',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        You're offline — changes will sync when back online
      </div>
    </div>
  );
}

export function WithQueuedMutations() {
  return (
    <div style={{ position: 'relative', height: '80px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div
        role="status"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          borderRadius: '9999px',
          border: '1px solid #FCD34D',
          background: '#FFFBEB',
          padding: '8px 16px',
          fontSize: '12px',
          fontWeight: 500,
          color: '#78350F',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        Syncing 3 queued changes…
      </div>
    </div>
  );
}
