import { PartnerApplicationForm } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '32px', background: '#0d1526', borderRadius: '12px', maxWidth: '560px' }}>
      <h2 style={{ color: '#f1f5f9', fontSize: '22px', fontWeight: 700, marginBottom: '8px' }}>
        Become a Varuflow Partner
      </h2>
      <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '24px' }}>
        Accounting firms earn 20% recurring revenue for every client they refer. Fill in the form below and we'll be in touch within 1 business day.
      </p>
      <PartnerApplicationForm />
    </div>
  );
}
