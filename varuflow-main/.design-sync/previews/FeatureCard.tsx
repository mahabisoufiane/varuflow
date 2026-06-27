import { FeatureCard } from 'varuflow-ui';
import { BarChart3, Package, Users, Zap, FileText, Globe } from 'lucide-react';

export function Basic() {
  return (
    <div style={{ padding: '16px', background: '#0d1526', borderRadius: '12px', maxWidth: '320px' }}>
      <FeatureCard
        icon={<BarChart3 size={20} />}
        title="Advanced Analytics"
        description="Real-time sales dashboards, revenue trends, and inventory turnover reports tailored for Nordic SMBs."
      />
    </div>
  );
}

export function WithBadge() {
  return (
    <div style={{ padding: '16px', background: '#0d1526', borderRadius: '12px', maxWidth: '320px' }}>
      <FeatureCard
        icon={<Zap size={20} />}
        title="AI Pricing Engine"
        description="Automatically suggest optimal prices based on demand, margins, and competitor data."
        badge="Pro"
      />
    </div>
  );
}

export function Grid() {
  const cards = [
    { icon: <FileText size={20} />, title: 'Smart Invoicing', description: 'Create and send compliant Nordic invoices in seconds. BAS chart of accounts built in.' },
    { icon: <Package size={20} />, title: 'Inventory Control', description: 'Track stock across multiple locations with automatic reorder alerts.' },
    { icon: <Users size={20} />, title: 'Customer CRM', description: 'Store purchase history, preferences, and important dates for every customer.' },
    { icon: <Globe size={20} />, title: 'Multi-currency', description: 'Sell in SEK, EUR, NOK, and DKK. Exchange rates update daily.' },
  ];
  return (
    <div style={{ padding: '16px', background: '#0d1526', borderRadius: '12px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        {cards.map((c) => (
          <FeatureCard key={c.title} icon={c.icon} title={c.title} description={c.description} />
        ))}
      </div>
    </div>
  );
}
