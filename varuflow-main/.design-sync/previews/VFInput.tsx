import { VFInput } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ width: 320, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <VFInput placeholder="Company name" />
      <VFInput type="email" placeholder="email@company.no" defaultValue="billing@nordic-sme.no" />
      <VFInput type="number" placeholder="0.00" />
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ width: 320 }}>
      <VFInput placeholder="Read-only value" disabled defaultValue="Locked field" />
    </div>
  );
}
