// frontend/src/lib/sanity/image.ts
// Sanity image URL builder wrapper.

import imageUrlBuilder from "@sanity/image-url";
import { getSanityClient, SANITY_ENABLED } from "./client";
import type { SanityImageSource } from "@sanity/image-url/lib/types/types";

let _builder: ReturnType<typeof imageUrlBuilder> | null = null;

function getBuilder() {
  if (!SANITY_ENABLED) return null;
  if (!_builder) {
    const client = getSanityClient();
    if (!client) return null;
    _builder = imageUrlBuilder(client);
  }
  return _builder;
}

export function urlFor(source: SanityImageSource) {
  return getBuilder()?.image(source);
}

export function urlForWidth(source: SanityImageSource, width: number) {
  return getBuilder()?.image(source).width(width).auto("format").url() ?? "";
}
