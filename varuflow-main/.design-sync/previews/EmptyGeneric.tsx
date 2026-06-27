import { EmptyState } from 'varuflow-ui';

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

export function Default() {
  return (
    <EmptyState
      illustration={<GenericIllustration />}
      title="Nothing to show here"
      description="This section is empty. Come back when there's something to display."
    />
  );
}

export function SearchEmpty() {
  return (
    <EmptyState
      illustration={<GenericIllustration />}
      title="No matches found"
      description="We couldn't find anything matching your search. Try different keywords."
      action={
        <button
          style={{
            background: 'transparent',
            color: '#4F46E5',
            border: '1px solid #4F46E5',
            borderRadius: '8px',
            padding: '8px 18px',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Clear search
        </button>
      }
    />
  );
}
