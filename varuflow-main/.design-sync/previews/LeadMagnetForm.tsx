import { LeadMagnetForm } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '480px' }}>
      <LeadMagnetForm
        title="2024 Nordic SMB Accounting Checklist"
        description="A 12-point checklist covering BAS chart of accounts, momsredovisning, and Bokföringslagen requirements. Used by 800+ Swedish businesses."
        pdfSlug="nordic-accounting-checklist-2024"
        buttonLabel="Download free checklist"
      />
    </div>
  );
}

export function InventoryGuide() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '480px' }}>
      <LeadMagnetForm
        title="Inventory Optimisation Guide for Wholesale"
        description="Learn how Nordic distributors cut overstock by 30% using simple reorder-point formulas and ABC analysis. Free 18-page PDF."
        pdfSlug="inventory-optimisation-wholesale"
      />
    </div>
  );
}
