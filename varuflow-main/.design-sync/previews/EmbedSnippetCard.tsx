import { EmbedSnippetCard } from 'varuflow-ui';

const snippet = `<iframe
  src="https://varuflow.vercel.app/widget/booking/acme-co"
  width="100%"
  height="600"
  frameborder="0"
  allow="payment"
></iframe>`;

export function Default() {
  return (
    <div style={{ padding: '24px', background: '#fff', maxWidth: '600px' }}>
      <EmbedSnippetCard
        snippet={snippet}
        url="https://varuflow.vercel.app/widget/booking/acme-co"
      />
    </div>
  );
}
