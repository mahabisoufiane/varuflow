import { MetricCard } from 'varuflow-ui';
import { TrendingUp, ShoppingCart, Users, Package } from 'lucide-react';

export function Revenue() {
  return (
    <div style={{ maxWidth: '380px', padding: '4px' }}>
      <MetricCard
        icon={TrendingUp}
        label="Revenue"
        value="124 850 kr"
        delta="8.2% vs last month"
        deltaType="up"
        colorClass="bg-indigo-100 text-indigo-700"
      />
    </div>
  );
}

export function Orders() {
  return (
    <div style={{ maxWidth: '380px', padding: '4px' }}>
      <MetricCard
        icon={ShoppingCart}
        label="Orders today"
        value="347"
        delta="3 fewer than yesterday"
        deltaType="down"
        colorClass="bg-amber-100 text-amber-700"
      />
    </div>
  );
}

export function Customers() {
  return (
    <div style={{ maxWidth: '380px', padding: '4px' }}>
      <MetricCard
        icon={Users}
        label="Active customers"
        value="1 204"
        colorClass="bg-emerald-100 text-emerald-700"
      />
    </div>
  );
}

export function Inventory() {
  return (
    <div style={{ maxWidth: '380px', padding: '4px' }}>
      <MetricCard
        icon={Package}
        label="Stock items"
        value="5 831"
        delta="unchanged"
        deltaType="zero"
        colorClass="bg-violet-100 text-violet-700"
      />
    </div>
  );
}
