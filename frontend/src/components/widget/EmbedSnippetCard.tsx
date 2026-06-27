"use client";

/**
 * Embed snippet preview + copy button — rendered inside the authed
 * "Settings → Booking → Embed" card so operators can grab the iframe
 * HTML to paste on their site. Kept in ``components/widget/`` so
 * both public and private pages can import it.
 */
import { useState } from "react";

export function EmbedSnippetCard({
  snippet,
  url,
}: {
  snippet: string;
  url: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    if (typeof navigator === "undefined") return;
    navigator.clipboard?.writeText(snippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">Embed on your website</h3>
        <button
          onClick={copy}
          className="rounded-md border px-3 py-1 text-sm hover:bg-accent"
        >
          {copied ? "Copied" : "Copy snippet"}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Paste the HTML below into your site. The widget is fully
        responsive and works without a Varuflow account.
      </p>
      <pre className="overflow-x-auto rounded bg-muted p-3 text-xs">
        <code>{snippet}</code>
      </pre>
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="text-xs underline text-muted-foreground"
      >
        Preview widget &rarr; {url}
      </a>
    </div>
  );
}
