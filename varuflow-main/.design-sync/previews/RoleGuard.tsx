// RoleGuard is a headless auth gate that fetches /api/auth/me and shows
// nothing while loading, or a "not authorised" panel when role insufficient.
// It requires network + a real session — floor card is correct.
export function Default() {
  return (
    <div style={{ padding: '16px', color: '#6B7280', fontSize: '14px' }}>
      RoleGuard — auth gate component, no visible output without a live session
    </div>
  );
}
