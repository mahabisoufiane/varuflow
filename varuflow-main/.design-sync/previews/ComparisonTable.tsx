import { ComparisonTable } from 'varuflow-ui';

const rows = [
  { feature: 'Invoicing', varuflow: 'Yes', competitor: 'Yes' },
  { feature: 'Inventory tracking', varuflow: 'Yes', competitor: 'No' },
  { feature: 'Multi-currency', varuflow: 'Yes', competitor: 'No' },
  { feature: 'Fortnox integration', varuflow: 'Yes', competitor: 'No' },
  { feature: 'AI pricing suggestions', varuflow: 'Yes', competitor: 'No' },
  { feature: 'Mobile app', varuflow: 'Yes', competitor: 'Yes' },
  { feature: 'Nordic VAT compliance', varuflow: 'Yes', competitor: 'Partial' },
  { feature: 'BankID login', varuflow: 'Yes', competitor: 'No' },
  { feature: 'EU data residency', varuflow: 'Yes', competitor: 'No' },
];

export function VsFortnox() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px' }}>
      <ComparisonTable competitorName="Fortnox" rows={rows} />
    </div>
  );
}
