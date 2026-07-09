// A module = a feature area gated by the product's require_module(<gate>)
// (backend middleware/plan_check.py). Names/copy come from the product's
// landing page (frontend/messages/{sv,en}.json) and capabilities reflect
// features verified to exist in the product.
export interface LocalizedText {
  sv: string;
  en: string;
}

export interface Capability {
  title: LocalizedText;
  description: LocalizedText;
}

export interface Module {
  slug: string;
  /** Real backend module gate name. */
  gate: string;
  name: LocalizedText;
  description: LocalizedText;
  valueProp: LocalizedText;
  capabilities: Capability[];
  /** Slugs of two modules this one works well with. */
  related: string[];
}
