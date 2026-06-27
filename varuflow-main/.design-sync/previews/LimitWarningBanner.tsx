import { LimitWarningBanner } from 'varuflow-ui';

export function ProductsWarning() {
  return (
    <div style={{ padding: '16px', maxWidth: '640px' }}>
      <LimitWarningBanner resource="products" current={42} limit={50} />
    </div>
  );
}

export function InvoicesWarning() {
  return (
    <div style={{ padding: '16px', maxWidth: '640px' }}>
      <LimitWarningBanner resource="invoices_per_month" current={95} limit={100} />
    </div>
  );
}

export function CustomersAtLimit() {
  return (
    <div style={{ padding: '16px', maxWidth: '640px' }}>
      <LimitWarningBanner resource="customers" current={198} limit={200} />
    </div>
  );
}
