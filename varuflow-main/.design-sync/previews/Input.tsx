import { Input } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ width: 320, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Input placeholder="Enter company name" />
      <Input type="email" placeholder="email@example.com" defaultValue="owner@nordic-sme.no" />
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ width: 320 }}>
      <Input placeholder="Cannot edit" disabled defaultValue="Locked value" />
    </div>
  );
}

export function Types() {
  return (
    <div style={{ width: 320, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Input type="number" placeholder="0.00" />
      <Input type="date" />
      <Input type="password" placeholder="••••••••" />
    </div>
  );
}
