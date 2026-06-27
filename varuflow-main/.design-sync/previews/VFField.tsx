import { VFField, VFInput, VFLabel, VFOptional } from 'varuflow-ui';

export function BasicField() {
  return (
    <div style={{ width: 340, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <VFField label="Company name" htmlFor="vf-company" required={false}>
        <VFInput id="vf-company" placeholder="Nordic SMB AS" />
      </VFField>
      <VFField label="Email" htmlFor="vf-email" hint="Invoices will be sent here.">
        <VFInput id="vf-email" type="email" placeholder="owner@company.no" />
      </VFField>
    </div>
  );
}

export function OptionalField() {
  return (
    <div style={{ width: 340 }}>
      <VFField label="Website" htmlFor="vf-website" optional hint="Used in customer-facing documents.">
        <VFInput id="vf-website" type="url" placeholder="https://company.no" />
      </VFField>
    </div>
  );
}

export function WithError() {
  return (
    <div style={{ width: 340 }}>
      <VFField label="VAT number" htmlFor="vf-vat" error="VAT number format is invalid — expected NO123456789MVA.">
        <VFInput id="vf-vat" defaultValue="BADFORMAT" />
      </VFField>
    </div>
  );
}
