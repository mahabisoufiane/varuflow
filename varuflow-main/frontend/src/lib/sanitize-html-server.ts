/**
 * Server-side HTML sanitizer for content rendered via dangerouslySetInnerHTML
 * in Server Components (SSG/ISR pages that must stay crawlable — no client
 * hydration delay).
 *
 * `@/lib/sanitize-html`'s sanitizeHtml() is DOMParser-based and only runs in
 * the browser (it returns "" during SSR) — it's the right tool for Client
 * Components (email template previews, campaign previews) but cannot be used
 * here without blanking the page on every request/build.
 *
 * Backed by the `sanitize-html` npm package (htmlparser2-based, pure JS, no
 * DOM dependency) — safe to run at build time and on the server.
 */
import sanitizeHtmlLib from "sanitize-html";

const ALLOWED_TAGS = [
  ...sanitizeHtmlLib.defaults.allowedTags,
  "img", // article bodies may embed inline images
];

const ALLOWED_ATTRIBUTES = {
  ...sanitizeHtmlLib.defaults.allowedAttributes,
  // `id` on headings/elements is required by TableOfContents, which does
  // document.getElementById(...) + <a href="#id"> scroll-spy navigation —
  // stripping it silently breaks that feature without erroring anywhere.
  "*": ["id"],
};

/**
 * Sanitize CMS/seed-authored article HTML before injecting it raw into the
 * DOM. Strips <script>, event handlers, javascript:/data: URIs, and any tag
 * not in the allowlist above, while preserving the heading anchors the blog
 * page's table-of-contents depends on.
 */
export function sanitizeArticleHtml(dirty: string): string {
  if (!dirty) return "";
  return sanitizeHtmlLib(dirty, {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: ALLOWED_ATTRIBUTES,
  });
}
