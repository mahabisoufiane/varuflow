import { EmptyState } from 'varuflow-ui';

const InventoryIllustration = () => (
  <svg viewBox="0 0 240 180" fill="none" style={{ width: '100%', height: 'auto' }} aria-hidden="true">
    <defs>
      <linearGradient id="vfBoxL2" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#A5B4FC" />
        <stop offset="100%" stopColor="#6366F1" />
      </linearGradient>
      <linearGradient id="vfBoxR2" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#6366F1" />
        <stop offset="100%" stopColor="#4338CA" />
      </linearGradient>
    </defs>
    <ellipse cx="120" cy="152" rx="84" ry="13" fill="#2563EB" fillOpacity="0.12" />
    <circle cx="44" cy="46" r="5" fill="#34D399" fillOpacity="0.7" />
    <circle cx="198" cy="38" r="7" fill="#A78BFA" fillOpacity="0.5" />
    <circle cx="208" cy="96" r="4" fill="#2563EB" fillOpacity="0.5" />
    <circle cx="38" cy="104" r="4" fill="#A78BFA" fillOpacity="0.45" />
    <rect x="103" y="26" width="34" height="28" rx="5" fill="#fff" fillOpacity="0.94" />
    <path d="M120 26 V54" stroke="#C7D2FE" strokeWidth="2.5" />
    <path d="M103 40 H137" stroke="#C7D2FE" strokeWidth="2.5" />
    <path d="M70 80 L120 98 V152 L70 134 Z" fill="url(#vfBoxL2)" />
    <path d="M170 80 L120 98 V152 L170 134 Z" fill="url(#vfBoxR2)" />
    <path d="M70 80 L120 62 L170 80 L120 98 Z" fill="#C7D2FE" />
    <path d="M120 62 V98" stroke="#fff" strokeOpacity="0.6" strokeWidth="2" />
  </svg>
);

export function Default() {
  return (
    <EmptyState
      illustration={<InventoryIllustration />}
      title="No products in inventory"
      description="Start building your catalogue by adding your first product or importing from a spreadsheet."
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
          Add product
        </button>
      }
    />
  );
}
