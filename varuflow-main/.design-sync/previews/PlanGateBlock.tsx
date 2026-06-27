import { PlanGateBlock } from 'varuflow-ui';

export function AnalyticsGate() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px' }}>
      <PlanGateBlock
        module="analytics"
        currentPlan="FREE"
        featureName="Advanced Analytics"
        description="Upgrade to PRO to unlock real-time dashboards, revenue trend charts, and customer LTV reports. You're currently on the FREE plan."
      />
    </div>
  );
}

export function ComplianceGate() {
  return (
    <div style={{ padding: '24px', background: '#0d1526', borderRadius: '12px' }}>
      <PlanGateBlock
        module="compliance"
        currentPlan="PRO"
        featureName="Compliance Suite"
        description="The Compliance Suite (SAF-T export, audit log, e-invoicing) requires the ENTERPRISE plan. You're on PRO."
      />
    </div>
  );
}
