/**
 * SlotPicker is a placeholder component that renders a plain text div.
 * The text was appearing blank possibly due to zero-height container.
 * We show it in a clearly sized wrapper.
 */

export function DefaultState() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px', fontFamily: 'system-ui, sans-serif' }}>
      <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#374151', marginBottom: '8px' }}>
        Available time slots
      </label>
      <div style={{ padding: '12px 16px', background: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '14px', color: '#6b7280' }}>
        Select a service and staff member to see available slots.
      </div>
    </div>
  );
}

export function WithContext() {
  const slots = ['09:00', '09:30', '10:00', '10:30', '11:00', '14:00', '14:30', '15:00'];
  return (
    <div style={{ padding: '16px', maxWidth: '480px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Service</label>
          <select style={{ height: '38px', width: '100%', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 10px', fontSize: '14px' }}>
            <option>Hårtvätt + klippning (45 min)</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Staff member</label>
          <select style={{ height: '38px', width: '100%', borderRadius: '8px', border: '1px solid #d1d5db', padding: '0 10px', fontSize: '14px' }}>
            <option>Anna Lindström</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Available slots — Wed 24 Jun</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
            {slots.map((slot, i) => (
              <button key={slot} style={{
                height: '40px', borderRadius: '8px', border: '1px solid ' + (i === 2 ? '#6366f1' : '#d1d5db'),
                background: i === 2 ? '#eef2ff' : '#fff', color: i === 2 ? '#4338ca' : '#374151',
                fontSize: '14px', fontWeight: i === 2 ? 600 : 400, cursor: 'pointer'
              }}>
                {slot}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
