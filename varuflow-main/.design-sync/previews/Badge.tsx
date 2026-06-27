import { Badge } from 'varuflow-ui';

export function Variants() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', padding: '8px' }}>
      <Badge variant="default">Active</Badge>
      <Badge variant="secondary">Pending</Badge>
      <Badge variant="destructive">Overdue</Badge>
      <Badge variant="outline">Draft</Badge>
    </div>
  );
}

export function InvoiceStatuses() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', padding: '8px' }}>
      <Badge variant="default">Paid</Badge>
      <Badge variant="secondary">Processing</Badge>
      <Badge variant="destructive">Failed</Badge>
      <Badge variant="outline">Voided</Badge>
    </div>
  );
}

export function PlanTiers() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', padding: '8px' }}>
      <Badge variant="outline">Free</Badge>
      <Badge variant="secondary">Starter</Badge>
      <Badge variant="default">Pro</Badge>
      <Badge variant="destructive">Suspended</Badge>
    </div>
  );
}
