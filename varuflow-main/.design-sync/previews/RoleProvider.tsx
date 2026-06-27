// RoleProvider is a context provider that fetches /api/auth/me on mount.
// It renders children transparently — no visual output of its own.
// Floor card is correct.
export function Default() {
  return (
    <div style={{ padding: '16px', color: '#6B7280', fontSize: '14px' }}>
      RoleProvider — context provider, no visible output
    </div>
  );
}
