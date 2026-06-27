// File: mobile/lib/stock-count-i18n.ts
// Purpose: Stock-count strings (Item 14). Keeps the table tiny and
// co-located with the feature rather than ballooning tablet-i18n.ts.
// Same `t(lang, key)` contract as tablet-i18n.ts so callers can swap.

export type StockCountKey =
  | "start"
  | "resume"
  | "submit"
  | "cancel"
  | "draft"
  | "pending_sync"
  | "synced"
  | "failed"
  | "scan_or_search"
  | "expected_qty"
  | "counted_qty"
  | "variance"
  | "note"
  | "sync_status"
  | "stock_count_synced"
  | "will_retry";

export const STOCK_COUNT_STRINGS: Record<
  "en" | "sv",
  Record<StockCountKey, string>
> = {
  en: {
    start:             "Start stock count",
    resume:            "Resume draft count",
    submit:            "Submit count",
    cancel:            "Cancel count",
    draft:             "Draft",
    pending_sync:      "Pending sync",
    synced:            "Synced",
    failed:            "Sync failed",
    scan_or_search:    "Scan or search product",
    expected_qty:      "Expected quantity",
    counted_qty:       "Counted quantity",
    variance:          "Variance",
    note:              "Note",
    sync_status:       "Sync status",
    stock_count_synced: "Stock count synced",
    will_retry:        "Will retry when online again",
  },
  sv: {
    start:             "Starta lagerinventering",
    resume:            "Fortsätt utkast",
    submit:            "Skicka inventering",
    cancel:            "Avbryt inventering",
    draft:             "Utkast",
    pending_sync:      "Väntar på synk",
    synced:            "Synkad",
    failed:            "Synkning misslyckades",
    scan_or_search:    "Skanna eller sök produkt",
    expected_qty:      "Förväntat antal",
    counted_qty:       "Räknat antal",
    variance:          "Differens",
    note:              "Anteckning",
    sync_status:       "Synkstatus",
    stock_count_synced: "Lagerinventering synkad",
    will_retry:        "Försöker igen när du är online",
  },
};

export function tStockCount(
  lang: string | null | undefined,
  key: StockCountKey,
): string {
  const normalized = (lang ?? "en").slice(0, 2).toLowerCase();
  const bundle =
    STOCK_COUNT_STRINGS[normalized as "en" | "sv"] ?? STOCK_COUNT_STRINGS.en;
  return bundle[key];
}
