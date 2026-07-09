/** Renders a JSON-LD block. Content is built from our own typed data —
 *  never from user input — so the inline script is safe. */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
