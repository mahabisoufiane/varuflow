/**
 * Client-side HTML sanitizer using the browser's native DOMParser.
 *
 * Strips all script elements, event-handler attributes, and javascript: hrefs.
 * Safe to use before dangerouslySetInnerHTML — prevents stored XSS from
 * user-authored HTML content (email templates, campaign bodies, SVG signatures).
 *
 * Must only be called in browser context ("use client" components or after mount).
 * Returns an empty string during SSR so pages hydrate correctly.
 */

const DANGEROUS_ELEMENTS = new Set([
  "script", "object", "embed", "applet", "base",
  "form", "input", "button", "select", "textarea",
  "iframe", "frame", "frameset", "link", "meta",
]);

const SVG_ALLOWED_ELEMENTS = new Set([
  "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
  "polygon", "text", "tspan", "defs", "use", "symbol", "clipPath",
  "linearGradient", "radialGradient", "stop", "filter", "feBlend",
  "feColorMatrix", "feComposite", "feFlood", "feGaussianBlur",
  "feMerge", "feMergeNode", "feOffset", "title", "desc",
]);

function stripDangerousAttributes(el: Element): void {
  const toRemove: string[] = [];
  for (const attr of Array.from(el.attributes)) {
    const name = attr.name.toLowerCase();
    const value = attr.value.toLowerCase().trim();
    // Remove all on* event handlers
    if (name.startsWith("on")) { toRemove.push(attr.name); continue; }
    // Remove javascript: and data: URIs in href/src/action/xlink:href
    if (["href", "src", "action", "xlink:href", "formaction"].includes(name)) {
      if (/^(javascript|data|vbscript):/i.test(value)) { toRemove.push(attr.name); continue; }
    }
    // Remove style attributes that contain expression() or url(javascript:)
    if (name === "style" && /expression\s*\(|javascript\s*:/i.test(value)) {
      toRemove.push(attr.name);
    }
  }
  for (const name of toRemove) el.removeAttribute(name);
}

export function sanitizeHtml(dirty: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") return "";
  if (!dirty) return "";

  const doc = new DOMParser().parseFromString(dirty, "text/html");

  // Remove all dangerous block-level elements (including nested)
  for (const tag of DANGEROUS_ELEMENTS) {
    doc.querySelectorAll(tag).forEach((el) => el.remove());
  }

  // Strip dangerous attributes from every remaining element
  doc.querySelectorAll("*").forEach(stripDangerousAttributes);

  return doc.body.innerHTML;
}

/**
 * Strict sanitizer for SVG data — allows only known SVG drawing elements.
 * Use this for user-captured signatures stored as SVG strings.
 */
export function sanitizeSvg(dirty: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") return "";
  if (!dirty) return "";

  const doc = new DOMParser().parseFromString(dirty, "image/svg+xml");
  const parseError = doc.querySelector("parsererror");
  if (parseError) return ""; // Malformed SVG — reject entirely

  // Remove any element that isn't in the allowed SVG set
  doc.querySelectorAll("*").forEach((el) => {
    if (!SVG_ALLOWED_ELEMENTS.has(el.tagName.toLowerCase())) {
      el.remove();
    } else {
      stripDangerousAttributes(el);
    }
  });

  return doc.documentElement.outerHTML;
}
