// File: mobile/lib/tablet-i18n.ts
// Purpose: Tiny string catalogue for Item 13 tablet chrome. The Expo
// app doesn't yet have a full i18n pipeline (the web app uses
// next-intl; mobile has no parallel). Rather than shipping a new
// dependency, we expose a pure `t(lang, key)` that reads from this
// file. `lang` defaults to the device locale via `expo-localization`
// — and falls back to English when the platform doesn't report one.

type TabletKey =
  | "sidebar_dashboard"
  | "sidebar_inventory"
  | "sidebar_analytics"
  | "sidebar_settings"
  | "topbar_search"
  | "topbar_quick_stats"
  | "layout_tablet";

export const TABLET_STRINGS: Record<"en" | "sv", Record<TabletKey, string>> = {
  en: {
    sidebar_dashboard: "Dashboard",
    sidebar_inventory: "Inventory",
    sidebar_analytics: "Analytics",
    sidebar_settings:  "Settings",
    topbar_search:     "Search",
    topbar_quick_stats: "Quick stats",
    layout_tablet:     "Tablet layout",
  },
  sv: {
    sidebar_dashboard: "Översikt",
    sidebar_inventory: "Lager",
    sidebar_analytics: "Analys",
    sidebar_settings:  "Inställningar",
    topbar_search:     "Sök",
    topbar_quick_stats: "Snabbstatistik",
    layout_tablet:     "Surfplattelayout",
  },
};

/** Resolves a tablet-chrome string. Falls back to English on unknown lang. */
export function t(lang: string | null | undefined, key: TabletKey): string {
  const normalized = (lang ?? "en").slice(0, 2).toLowerCase();
  const bundle = TABLET_STRINGS[normalized as "en" | "sv"] ?? TABLET_STRINGS.en;
  return bundle[key];
}
