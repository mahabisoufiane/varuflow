import { VFOptional, VFLabel } from 'varuflow-ui';

export function Standalone() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Website</span>
      <VFOptional />
    </div>
  );
}

export function InLabel() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <VFLabel>
        Twitter handle <VFOptional />
      </VFLabel>
      <VFLabel>
        Secondary email <VFOptional />
      </VFLabel>
    </div>
  );
}
