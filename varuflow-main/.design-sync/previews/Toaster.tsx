// Toaster is an invisible container mounted at root; it has no visual output
// until a toast() call fires. A floor card is the correct preview.
export function Default() {
  return (
    <div style={{ padding: '16px', color: '#6B7280', fontSize: '14px' }}>
      Toaster — toast container, no visible output until toast() is triggered
    </div>
  );
}
