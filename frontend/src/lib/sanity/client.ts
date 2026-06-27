// frontend/src/lib/sanity/client.ts
// Sanity GROQ client. Falls back to seed data when not configured.

import { createClient, type SanityClient } from "@sanity/client";

export const SANITY_PROJECT_ID = process.env.NEXT_PUBLIC_SANITY_PROJECT_ID ?? "";
export const SANITY_DATASET = process.env.NEXT_PUBLIC_SANITY_DATASET ?? "production";
export const SANITY_API_VERSION = "2024-05-01";

export const SANITY_ENABLED = !!SANITY_PROJECT_ID;

let _client: SanityClient | null = null;

export function getSanityClient(): SanityClient | null {
  if (!SANITY_ENABLED) return null;
  if (!_client) {
    _client = createClient({
      projectId: SANITY_PROJECT_ID,
      dataset: SANITY_DATASET,
      apiVersion: SANITY_API_VERSION,
      useCdn: process.env.NODE_ENV === "production",
      // No token needed for public read-only queries
    });
  }
  return _client;
}

/** Fetch via GROQ — server-side only, not a hook. */
export async function sanityFetch<T>(
  query: string,
  params?: Record<string, unknown>,
): Promise<T | null> {
  const client = getSanityClient();
  if (!client) return null;
  return client.fetch<T>(query, params ?? {}, {
    // ISR: Next will cache this via fetch, revalidate every 60 min
    next: { revalidate: 3600 },
  });
}
