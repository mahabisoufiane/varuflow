// frontend/src/lib/sanity/queries.ts
// Typed GROQ queries for the blog.

export const POST_SUMMARY_FIELDS = `
  _id,
  _type,
  "slug": slug.current,
  title,
  excerpt,
  locale,
  publishedAt,
  updatedAt,
  "readingTimeMinutes": round(length(pt::text(body)) / 1000),
  category->{title, "slug": slug.current},
  "tags": tags[]->{label, "slug": slug.current},
  "author": author->{name, role, photo, initials},
  featuredImage{asset, alt, caption},
  seoTitle,
  seoDescription,
`;

export const POST_FULL_FIELDS = `
  ${POST_SUMMARY_FIELDS}
  body[]{
    ...,
    _type == "image" => {
      ...,
      asset->
    }
  },
  leadMagnet,
  canonicalUrl,
  "relatedArticles": relatedArticles[]->{
    ${POST_SUMMARY_FIELDS}
  },
  "translations": translations[]{locale, slug},
`;

export const QUERY_ALL_POSTS = (locale?: string) => `
  *[_type == "post"${locale ? ` && locale == "${locale}"` : ""} && defined(publishedAt)]
  | order(publishedAt desc) {
    ${POST_SUMMARY_FIELDS}
  }
`;

export const QUERY_POSTS_PAGINATED = `
  *[_type == "post" && defined(publishedAt) && (!defined($locale) || locale == $locale)]
  | order(publishedAt desc) [$from..$to] {
    ${POST_SUMMARY_FIELDS}
  }
`;

export const QUERY_POSTS_COUNT = `
  count(*[_type == "post" && defined(publishedAt) && (!defined($locale) || locale == $locale)])
`;

export const QUERY_POST_BY_SLUG = `
  *[_type == "post" && slug.current == $slug][0] {
    ${POST_FULL_FIELDS}
  }
`;

export const QUERY_POSTS_BY_CATEGORY = `
  *[_type == "post" && defined(publishedAt) && category->slug.current == $categorySlug
    && (!defined($locale) || locale == $locale)]
  | order(publishedAt desc) {
    ${POST_SUMMARY_FIELDS}
  }
`;

export const QUERY_POSTS_BY_TAG = `
  *[_type == "post" && defined(publishedAt) && $tagSlug in tags[]->slug.current
    && (!defined($locale) || locale == $locale)]
  | order(publishedAt desc) {
    ${POST_SUMMARY_FIELDS}
  }
`;

export const QUERY_ALL_POST_SLUGS = `
  *[_type == "post" && defined(publishedAt)] { "slug": slug.current, locale }
`;

export const QUERY_ALL_CATEGORY_SLUGS = `
  *[_type == "category"] { "slug": slug.current }
`;

export const QUERY_ALL_TAG_SLUGS = `
  *[_type == "tag"] { "slug": slug.current }
`;

export const QUERY_SITEMAP_POSTS = `
  *[_type == "post" && defined(publishedAt)] {
    "slug": slug.current,
    locale,
    publishedAt,
    updatedAt,
    "translations": translations[]{locale, slug},
  }
`;
