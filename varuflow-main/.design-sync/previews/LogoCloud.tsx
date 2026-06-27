import { LogoCloud } from 'varuflow-ui';

export function Default() {
  return (
    <div style={{ background: '#0d1526', borderRadius: '12px', overflow: 'hidden' }}>
      <LogoCloud />
    </div>
  );
}

export function CustomLogos() {
  return (
    <div style={{ background: '#0d1526', borderRadius: '12px', overflow: 'hidden' }}>
      <LogoCloud
        title="Trusted by 2,000+ Nordic businesses"
        logos={[
          { name: 'Kvickly Partner', description: 'Danish retail chain' },
          { name: 'Byggmax Group', description: 'Swedish DIY retail' },
          { name: 'Nordic Nest', description: 'Nordic e-commerce' },
          { name: 'Ahlsell SE', description: 'Technical distributor' },
          { name: 'Jollyroom', description: 'Children products' },
          { name: 'Dustin Group', description: 'IT products & services' },
        ]}
      />
    </div>
  );
}
