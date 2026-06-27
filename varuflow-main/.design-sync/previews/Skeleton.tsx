import { Skeleton } from 'varuflow-ui';

export function TextLines() {
  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '320px' }}>
      <Skeleton style={{ height: '20px', width: '80%' }} />
      <Skeleton style={{ height: '16px', width: '100%' }} />
      <Skeleton style={{ height: '16px', width: '92%' }} />
      <Skeleton style={{ height: '16px', width: '60%' }} />
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div style={{ padding: '16px', maxWidth: '340px' }}>
      <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <Skeleton style={{ height: '20px', width: '55%' }} />
        <Skeleton style={{ height: '14px', width: '75%' }} />
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          <Skeleton style={{ height: '36px', flex: 1 }} />
          <Skeleton style={{ height: '36px', flex: 1 }} />
        </div>
      </div>
    </div>
  );
}

export function AvatarAndText() {
  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '320px' }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Skeleton style={{ width: '40px', height: '40px', borderRadius: '50%', flexShrink: 0 }} />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <Skeleton style={{ height: '14px', width: '60%' }} />
            <Skeleton style={{ height: '12px', width: '85%' }} />
          </div>
        </div>
      ))}
    </div>
  );
}
