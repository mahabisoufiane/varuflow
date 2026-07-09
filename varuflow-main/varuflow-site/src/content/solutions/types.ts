// Target verticals. Base copy sourced from the product's vertical landing
// pages (frontend .../verticals/[vertical]/verticals.ts); pain points map
// each vertical's problems onto real product modules.
import type { LocalizedText } from "../modules/types";

export interface PainPoint {
  pain: LocalizedText;
  detail: LocalizedText;
  solution: LocalizedText;
  /** Slug of the module that solves this pain (content/modules). */
  moduleSlug: string;
}

export interface Solution {
  slug: string;
  eyebrow: LocalizedText;
  headline: LocalizedText;
  subheadline: LocalizedText;
  painPoints: PainPoint[];
  compliance: LocalizedText;
}
