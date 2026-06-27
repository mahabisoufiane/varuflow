import { VFTextarea } from 'varuflow-ui';

export function Basic() {
  return (
    <div style={{ padding: '16px', maxWidth: '400px' }}>
      <VFTextarea placeholder="Enter a description…" />
    </div>
  );
}

export function WithValue() {
  return (
    <div style={{ padding: '16px', maxWidth: '400px' }}>
      <VFTextarea
        defaultValue="This customer has been with us since 2021. Prefers email contact. Always pays on time."
        rows={4}
      />
    </div>
  );
}

export function Disabled() {
  return (
    <div style={{ padding: '16px', maxWidth: '400px' }}>
      <VFTextarea
        disabled
        defaultValue="Read-only notes content goes here."
        rows={3}
      />
    </div>
  );
}
