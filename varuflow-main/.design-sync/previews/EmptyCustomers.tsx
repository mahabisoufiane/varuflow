import { EmptyState } from 'varuflow-ui';

const CustomersIllustration = () => (
  <svg viewBox="0 0 240 180" fill="none" style={{ width: '100%', height: 'auto' }} aria-hidden="true">
    <defs>
      <linearGradient id="vfCardC2" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#312E81" />
        <stop offset="100%" stopColor="#1E1B4B" />
      </linearGradient>
      <linearGradient id="vfAv12" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#60A5FA" />
        <stop offset="100%" stopColor="#6366F1" />
      </linearGradient>
      <linearGradient id="vfAv22" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#34D399" />
        <stop offset="100%" stopColor="#10B981" />
      </linearGradient>
    </defs>
    <ellipse cx="120" cy="154" rx="80" ry="12" fill="#2563EB" fillOpacity="0.12" />
    <circle cx="46" cy="44" r="6" fill="#A78BFA" fillOpacity="0.5" />
    <circle cx="198" cy="40" r="5" fill="#34D399" fillOpacity="0.6" />
    <rect x="74" y="58" width="92" height="62" rx="12" fill="#2563EB" fillOpacity="0.18" transform="rotate(-6 120 90)" />
    <rect x="66" y="64" width="108" height="66" rx="12" fill="url(#vfCardC2)" />
    <circle cx="92" cy="92" r="15" fill="url(#vfAv12)" />
    <circle cx="118" cy="92" r="15" fill="url(#vfAv22)" />
    <rect x="84" y="114" width="72" height="5" rx="2.5" fill="#fff" fillOpacity="0.22" />
    <rect x="98" y="124" width="44" height="4" rx="2" fill="#fff" fillOpacity="0.14" />
  </svg>
);

export function Default() {
  return (
    <EmptyState
      illustration={<CustomersIllustration />}
      title="No customers yet"
      description="Add your first customer to start managing contacts, invoices, and sales."
      action={
        <button
          style={{
            background: '#4F46E5',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Add customer
        </button>
      }
    />
  );
}
