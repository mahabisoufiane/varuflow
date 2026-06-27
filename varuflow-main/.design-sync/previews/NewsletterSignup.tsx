import { NewsletterSignup } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px' }}>
      <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '12px' }}>
        Get the Nordic Accounting Checklist — free
      </p>
      <NewsletterSignup />
    </div>
  );
}

export function Compact() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px', maxWidth: '280px' }}>
      <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '12px' }}>
        Weekly SMB tips
      </p>
      <NewsletterSignup compact />
    </div>
  );
}
