import { defineField, defineType } from "sanity";
import { DocumentTextIcon } from "@sanity/icons";

const LEAD_MAGNET_TYPE = defineType({
  name: "leadMagnet",
  title: "Lead magnet",
  type: "object",
  fields: [
    defineField({ name: "title", type: "string", title: "Title", validation: (R) => R.required() }),
    defineField({ name: "description", type: "text", title: "Description", rows: 2 }),
    defineField({ name: "pdfSlug", type: "slug", title: "PDF slug (for download URL)", options: { source: "title" } }),
    defineField({ name: "buttonLabel", type: "string", title: "Button label", initialValue: "Download free PDF" }),
  ],
});

export default defineType({
  name: "post",
  title: "Blog post",
  type: "document",
  icon: DocumentTextIcon,
  fields: [
    // ── Core ──────────────────────────────────────────────────
    defineField({ name: "title", type: "string", title: "Title", validation: (R) => R.required().max(100) }),
    defineField({
      name: "slug",
      type: "slug",
      title: "Slug",
      options: { source: "title" },
      validation: (R) => R.required(),
    }),
    defineField({
      name: "locale",
      type: "string",
      title: "Locale",
      options: {
        list: [
          { title: "English", value: "en" },
          { title: "Swedish", value: "sv" },
          { title: "Arabic", value: "ar" },
          { title: "French", value: "fr" },
        ],
        layout: "radio",
      },
      initialValue: "en",
      validation: (R) => R.required(),
    }),
    defineField({
      name: "translations",
      type: "array",
      title: "Translations (other locales)",
      of: [
        {
          type: "object",
          fields: [
            defineField({ name: "locale", type: "string", title: "Locale" }),
            defineField({ name: "slug", type: "string", title: "Slug in that locale" }),
          ],
        },
      ],
    }),

    // ── Classification ─────────────────────────────────────────
    defineField({
      name: "category",
      type: "reference",
      to: [{ type: "category" }],
      title: "Category",
      validation: (R) => R.required(),
    }),
    defineField({
      name: "tags",
      type: "array",
      title: "Tags",
      of: [{ type: "reference", to: [{ type: "tag" }] }],
    }),

    // ── Meta ───────────────────────────────────────────────────
    defineField({ name: "excerpt", type: "text", title: "Excerpt (description)", rows: 2, validation: (R) => R.required().max(165) }),
    defineField({ name: "author", type: "reference", to: [{ type: "author" }], title: "Author" }),
    defineField({ name: "publishedAt", type: "datetime", title: "Published at", validation: (R) => R.required() }),
    defineField({ name: "updatedAt", type: "datetime", title: "Last updated at" }),
    defineField({
      name: "featuredImage",
      type: "image",
      title: "Featured image",
      options: { hotspot: true },
      fields: [
        defineField({ name: "alt", type: "string", title: "Alt text", validation: (R) => R.required() }),
        defineField({ name: "caption", type: "string", title: "Caption" }),
      ],
    }),

    // ── Body ───────────────────────────────────────────────────
    defineField({
      name: "body",
      type: "array",
      title: "Body",
      of: [
        {
          type: "block",
          styles: [
            { title: "Normal", value: "normal" },
            { title: "H2", value: "h2" },
            { title: "H3", value: "h3" },
            { title: "H4", value: "h4" },
            { title: "Quote", value: "blockquote" },
          ],
          marks: {
            decorators: [
              { title: "Bold", value: "strong" },
              { title: "Italic", value: "em" },
              { title: "Code", value: "code" },
            ],
            annotations: [
              {
                name: "link",
                type: "object",
                title: "Link",
                fields: [
                  defineField({ name: "href", type: "url", title: "URL", validation: (R) => R.uri({ allowRelative: true }) }),
                  defineField({ name: "blank", type: "boolean", title: "Open in new tab", initialValue: false }),
                ],
              },
              {
                name: "internalLink",
                type: "object",
                title: "Internal link",
                fields: [
                  defineField({ name: "href", type: "string", title: "Path (e.g. /en/pricing)" }),
                ],
              },
            ],
          },
        },
        // Code blocks
        {
          type: "object",
          name: "codeBlock",
          title: "Code block",
          fields: [
            defineField({ name: "language", type: "string", title: "Language", initialValue: "bash" }),
            defineField({ name: "code", type: "text", title: "Code" }),
            defineField({ name: "filename", type: "string", title: "Filename (optional)" }),
          ],
        },
        // Images
        {
          type: "image",
          options: { hotspot: true },
          fields: [
            defineField({ name: "alt", type: "string", title: "Alt text" }),
            defineField({ name: "caption", type: "string", title: "Caption" }),
          ],
        },
        // Callout / lead magnet CTA
        {
          type: "object",
          name: "callout",
          title: "Callout box",
          fields: [
            defineField({ name: "variant", type: "string", options: { list: ["info", "warning", "success", "tip"] } }),
            defineField({ name: "body", type: "text", title: "Content" }),
          ],
        },
      ],
    }),

    // ── SEO ────────────────────────────────────────────────────
    defineField({ name: "seoTitle", type: "string", title: "SEO title (≤60 chars)", validation: (R) => R.max(60) }),
    defineField({ name: "seoDescription", type: "text", title: "SEO description (≤155 chars)", rows: 2, validation: (R) => R.max(155) }),
    defineField({ name: "canonicalUrl", type: "url", title: "Canonical URL (leave blank for auto)", validation: (R) => R.uri({ allowRelative: true }) }),

    // ── Conversion ─────────────────────────────────────────────
    defineField({ name: "leadMagnet", ...LEAD_MAGNET_TYPE, title: "Lead magnet" }),
    defineField({
      name: "relatedArticles",
      type: "array",
      title: "Related articles",
      of: [{ type: "reference", to: [{ type: "post" }] }],
      validation: (R) => R.max(4),
    }),
  ],

  orderings: [
    { title: "Published (newest first)", name: "publishedAtDesc", by: [{ field: "publishedAt", direction: "desc" }] },
  ],

  preview: {
    select: {
      title: "title",
      subtitle: "excerpt",
      media: "featuredImage",
    },
  },
});
