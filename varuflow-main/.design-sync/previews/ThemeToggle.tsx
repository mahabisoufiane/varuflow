import { ThemeProvider, ThemeToggle } from 'varuflow-ui';

export function LightMode() {
  return (
    <div style={{ padding: '24px', display: 'flex', alignItems: 'center', gap: '16px' }}>
      <ThemeProvider defaultTheme="light">
        <ThemeToggle />
      </ThemeProvider>
      <span style={{ fontSize: '13px', color: '#64748b' }}>Light mode</span>
    </div>
  );
}

export function DarkMode() {
  return (
    <div style={{ padding: '24px', display: 'flex', alignItems: 'center', gap: '16px', background: '#0f172a', borderRadius: '8px' }}>
      <ThemeProvider defaultTheme="dark">
        <ThemeToggle />
      </ThemeProvider>
      <span style={{ fontSize: '13px', color: '#94a3b8' }}>Dark mode</span>
    </div>
  );
}
