/**
 * BookingCalendar uses cn() from @/lib/utils. Write static reproduction.
 */

const appointments = [
  { id: 'a1', start_time: '2026-06-24T09:00:00', end_time: '2026-06-24T09:45:00', status: 'confirmed', channel: 'online' },
  { id: 'a2', start_time: '2026-06-24T11:00:00', end_time: '2026-06-24T11:30:00', status: 'booked', channel: 'walk-in' },
  { id: 'a3', start_time: '2026-06-24T14:00:00', end_time: '2026-06-24T15:00:00', status: 'cancelled', channel: 'phone' },
  { id: 'a4', start_time: '2026-06-24T15:30:00', end_time: '2026-06-24T16:00:00', status: 'no_show', channel: 'online' },
];

const STATUS_STYLES: Record<string, { background: string; color: string }> = {
  booked: { background: '#dbeafe', color: '#1d4ed8' },
  confirmed: { background: '#d1fae5', color: '#065f46' },
  completed: { background: '#f3f4f6', color: '#374151' },
  cancelled: { background: '#fee2e2', color: '#b91c1c' },
  no_show: { background: '#fef3c7', color: '#92400e' },
  waitlisted: { background: '#ede9fe', color: '#5b21b6' },
};

export function WithAppointments() {
  return (
    <div style={{ padding: '16px', maxWidth: '600px', fontFamily: 'system-ui, sans-serif' }}>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {appointments.map((a) => {
          const style = STATUS_STYLES[a.status] ?? { background: '#f3f4f6', color: '#374151' };
          return (
            <li key={a.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderRadius: '12px', border: '1px solid #e5e7eb', background: '#fff', padding: '12px' }}>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827', marginBottom: '2px' }}>
                  {new Date(a.start_time).toLocaleString('sv-SE')}
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                  {a.channel} · ends {new Date(a.end_time).toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
              <span style={{ ...style, borderRadius: '9999px', padding: '4px 10px', fontSize: '12px', fontWeight: 500 }}>
                {a.status}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function LoadingState() {
  return (
    <div style={{ padding: '16px', maxWidth: '600px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ height: '64px', borderRadius: '12px', background: '#f3f4f6', animation: 'pulse 2s infinite' }} />
        ))}
      </div>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }`}</style>
    </div>
  );
}

export function EmptyState() {
  return (
    <div style={{ padding: '16px', maxWidth: '600px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ borderRadius: '16px', border: '1px dashed #d1d5db', padding: '32px', textAlign: 'center', fontSize: '14px', color: '#9ca3af' }}>
        No appointments yet.
      </div>
    </div>
  );
}
