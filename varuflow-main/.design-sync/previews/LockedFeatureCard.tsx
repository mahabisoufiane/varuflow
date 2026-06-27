import { LockedFeatureCard } from 'varuflow-ui';

export function ProFeature() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <LockedFeatureCard
        featureName="White-label branding"
        requiredPlan="PRO"
        description="Customise the logo, colours and domain name for your customer portal."
      />
    </div>
  );
}

export function EnterpriseFeature() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <LockedFeatureCard
        featureName="Webhook integrations"
        requiredPlan="ENTERPRISE"
        description="Push real-time events to your own systems via HTTPS webhooks."
      >
        <div style={{ padding: '24px', display: 'flex', gap: '12px', flexDirection: 'column' }}>
          <div style={{ height: '16px', background: '#e5e7eb', borderRadius: '4px', width: '60%' }} />
          <div style={{ height: '12px', background: '#f3f4f6', borderRadius: '4px', width: '80%' }} />
          <div style={{ height: '12px', background: '#f3f4f6', borderRadius: '4px', width: '70%' }} />
        </div>
      </LockedFeatureCard>
    </div>
  );
}

export function ProApiAccess() {
  return (
    <div style={{ padding: '16px', maxWidth: '480px' }}>
      <LockedFeatureCard
        featureName="REST API access"
        requiredPlan="PRO"
        description="Connect your e-commerce, ERP and custom tools via the Varuflow REST API."
      />
    </div>
  );
}
