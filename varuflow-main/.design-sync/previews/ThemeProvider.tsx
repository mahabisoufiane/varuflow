// ThemeProvider is a context provider with no visible output of its own.
// It is tested via integration with child components — a floor card is correct.
export function Default() {
  return (
    <div style={{ padding: '16px', color: '#6B7280', fontSize: '14px' }}>
      ThemeProvider — context provider, no visible output
    </div>
  );
}
