import { Button } from 'varuflow-ui';

export function Variants() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', padding: '8px' }}>
      <Button variant="primary">Save changes</Button>
      <Button variant="secondary">Cancel</Button>
      <Button variant="ghost">View details</Button>
      <Button variant="danger">Delete</Button>
      <Button variant="success">Confirm</Button>
    </div>
  );
}

export function Sizes() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', padding: '8px' }}>
      <Button variant="primary" size="sm">Small</Button>
      <Button variant="primary" size="default">Default</Button>
      <Button variant="primary" size="lg">Large</Button>
    </div>
  );
}

export function States() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', padding: '8px' }}>
      <Button variant="primary" loading>Saving…</Button>
      <Button variant="primary" disabled>Disabled</Button>
      <Button variant="secondary" disabled>Can't cancel</Button>
    </div>
  );
}

export function Outline() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', padding: '8px' }}>
      <Button variant="outline">Export PDF</Button>
      <Button variant="link">View full report</Button>
    </div>
  );
}
