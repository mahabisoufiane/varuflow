import { VFLabel, VFOptional } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <VFLabel>Company name</VFLabel>
      <VFLabel>Organisation number</VFLabel>
      <VFLabel>VAT number</VFLabel>
    </div>
  );
}

export function WithOptional() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <VFLabel>
        Website <VFOptional />
      </VFLabel>
      <VFLabel>
        Internal notes <VFOptional />
      </VFLabel>
    </div>
  );
}
