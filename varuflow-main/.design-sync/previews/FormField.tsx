import { FormField } from 'varuflow-ui';

export function TextInput() {
  return (
    <div style={{ width: 340, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <FormField
        name="company"
        label="Company name"
        placeholder="Nordic SMB AS"
        required
      />
      <FormField
        name="email"
        kind="email"
        label="Email address"
        placeholder="owner@company.no"
        hint="We'll send invoices to this address."
      />
    </div>
  );
}

export function SelectField() {
  return (
    <div style={{ width: 340 }}>
      <FormField
        name="payment_terms"
        kind="select"
        label="Payment terms"
        placeholder="Choose terms…"
        options={[
          { value: 'net14', label: 'Net 14 days' },
          { value: 'net30', label: 'Net 30 days' },
          { value: 'net60', label: 'Net 60 days' },
          { value: 'prepaid', label: 'Prepaid' },
        ]}
      />
    </div>
  );
}

export function WithError() {
  return (
    <div style={{ width: 340, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <FormField
        name="vat"
        label="VAT number"
        placeholder="NO123456789MVA"
        error="VAT number format is invalid."
        defaultValue="BADVALUE"
      />
      <FormField
        name="notes"
        kind="textarea"
        label="Internal notes"
        placeholder="Add any relevant notes…"
        rows={3}
      />
    </div>
  );
}

export function CheckboxToggle() {
  return (
    <div style={{ width: 340, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <FormField
        name="send_reminders"
        kind="checkbox"
        label="Send automatic payment reminders"
        hint="Reminders go out 3 and 7 days after due date."
        defaultChecked
      />
      <FormField
        name="auto_invoice"
        kind="toggle"
        label="Enable automatic invoicing"
        hint="Generates invoices on the 1st of each month."
      />
    </div>
  );
}
