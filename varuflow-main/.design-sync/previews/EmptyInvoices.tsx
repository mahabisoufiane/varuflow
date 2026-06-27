import { EmptyState } from 'varuflow-ui';

const InvoicesIllustration = () => (
  <svg viewBox="0 0 240 180" fill="none" style={{ width: '100%', height: 'auto' }} aria-hidden="true">
    <defs>
      <linearGradient id="vfDoc2" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#EEF2FF" />
        <stop offset="100%" stopColor="#C7D2FE" />
      </linearGradient>
    </defs>
    <ellipse cx="120" cy="156" rx="78" ry="12" fill="#2563EB" fillOpacity="0.12" />
    <circle cx="52" cy="40" r="6" fill="#A78BFA" fillOpacity="0.5" />
    <circle cx="196" cy="52" r="5" fill="#34D399" fillOpacity="0.65" />
    <circle cx="44" cy="118" r="4" fill="#2563EB" fillOpacity="0.45" />
    <path d="M84 34 H146 L168 56 V150 H84 Z" fill="url(#vfDoc2)" />
    <path d="M146 34 V56 H168 Z" fill="#A5B4FC" />
    <rect x="98" y="72" width="56" height="6" rx="3" fill="#60A5FA" fillOpacity="0.9" />
    <rect x="98" y="88" width="40" height="5" rx="2.5" fill="#A5B4FC" />
    <rect x="98" y="100" width="46" height="5" rx="2.5" fill="#A5B4FC" />
    <rect x="98" y="118" width="30" height="5" rx="2.5" fill="#A5B4FC" />
    <circle cx="158" cy="132" r="18" fill="#34D399" />
    <path d="M150 132 l6 6 l10 -12" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function Default() {
  return (
    <EmptyState
      illustration={<InvoicesIllustration />}
      title="No invoices yet"
      description="Create your first invoice and get paid faster with automated reminders."
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
          Create invoice
        </button>
      }
    />
  );
}
