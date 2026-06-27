import { FormSection, FormField } from 'varuflow-ui';

export function BasicSection() {
  return (
    <div style={{ width: 680, padding: 16 }}>
      <FormSection title="Company details" description="Basic information about your organisation.">
        <FormField name="name" label="Company name" placeholder="Nordic SMB AS" required />
        <FormField name="org_no" label="Organisation number" placeholder="123 456 789" />
        <FormField name="vat" label="VAT number" placeholder="NO123456789MVA" />
        <FormField name="email" kind="email" label="Billing email" placeholder="billing@company.no" />
      </FormSection>
    </div>
  );
}

export function NoTitle() {
  return (
    <div style={{ width: 680, padding: 16 }}>
      <FormSection>
        <FormField name="address" label="Street address" placeholder="Storgata 1" />
        <FormField name="city" label="City" placeholder="Oslo" />
        <FormField name="postal" label="Postal code" placeholder="0150" />
        <FormField
          name="country"
          kind="select"
          label="Country"
          placeholder="Select country…"
          options={[
            { value: 'NO', label: 'Norway' },
            { value: 'SE', label: 'Sweden' },
            { value: 'DK', label: 'Denmark' },
            { value: 'FI', label: 'Finland' },
          ]}
        />
      </FormSection>
    </div>
  );
}
