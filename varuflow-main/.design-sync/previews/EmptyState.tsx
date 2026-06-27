import { EmptyState } from 'varuflow-ui';

// Inline illustration SVG — EmptyState accepts any React node as illustration
const GenericIllustration = () => (
  <svg viewBox="0 0 240 180" fill="none" style={{ width: '100%', height: 'auto' }} aria-hidden="true">
    <ellipse cx="120" cy="152" rx="76" ry="12" fill="#2563EB" fillOpacity="0.12" />
    <circle cx="50" cy="48" r="6" fill="#A78BFA" fillOpacity="0.5" />
    <circle cx="192" cy="54" r="5" fill="#34D399" fillOpacity="0.6" />
    <circle cx="110" cy="86" r="38" stroke="#6366F1" strokeWidth="10" fill="none" />
    <path d="M138 114 l24 24" stroke="#6366F1" strokeWidth="11" strokeLinecap="round" />
    <circle cx="110" cy="86" r="20" fill="#2563EB" fillOpacity="0.12" />
  </svg>
);

export function WithAction() {
  return (
    <EmptyState
      illustration={<GenericIllustration />}
      title="No results found"
      description="Try adjusting your search or filters to find what you're looking for."
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
          Clear filters
        </button>
      }
    />
  );
}

export function WithoutAction() {
  return (
    <EmptyState
      illustration={<GenericIllustration />}
      title="Nothing here yet"
      description="Data will appear here once your team starts using this feature."
    />
  );
}

export function MinimalNoDescription() {
  return (
    <EmptyState
      illustration={<GenericIllustration />}
      title="All caught up!"
    />
  );
}
