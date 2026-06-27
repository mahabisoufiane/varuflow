import { StatBar } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ background: '#0d1526', borderRadius: '12px', overflow: 'hidden' }}>
      <StatBar />
    </div>
  );
}

export function CustomStats() {
  return (
    <div style={{ background: '#0d1526', borderRadius: '12px', overflow: 'hidden' }}>
      <StatBar
        stats={[
          { value: '2,000+', label: 'SMBs using Varuflow' },
          { value: '4.9/5', label: 'G2 rating' },
          { value: '99.9%', label: 'Uptime SLA' },
          { value: '< 2 h', label: 'Avg. onboarding time' },
        ]}
      />
    </div>
  );
}
