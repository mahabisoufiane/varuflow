// File: mobile/lib/stock-count.ts
// Purpose: Offline-first local storage for stock-count drafts (Item 14)
// Used by:  StockCountSheet, inventory.tsx, stock-count-sync.ts
//
// Drafts are persisted in AsyncStorage under a single JSON array so a
// single read/write cycle covers the whole list. This keeps the code
// simple and avoids the transactional semantics we don't need here —
// the mobile app is the only writer, the user counts one draft at a
// time, and conflicts between drafts are impossible by design.

import AsyncStorage from "@react-native-async-storage/async-storage";

export const STOCK_COUNT_STORAGE_KEY = "@varuflow:stock-counts";

export type StockCountStatus =
  | "draft"
  | "submitted"
  | "synced"
  | "failed";

export interface StockCountItem {
  id: string;
  productId: string;
  barcode?: string;
  productName: string;
  expectedQty: number;
  countedQty: number;
  note?: string;
  batchId?: string;
}

export interface StockCountDraft {
  id: string;
  orgId: string;
  warehouseId: string;
  sessionId: string;
  createdAt: string;
  updatedAt: string;
  status: StockCountStatus;
  items: StockCountItem[];
  lastError?: string;
}

// ── Internal helpers ──────────────────────────────────────────────────

function uid(): string {
  // RFC 4122-ish v4 from Math.random — good enough for client-side row
  // ids that the backend accepts verbatim. Not a cryptographic UUID.
  const hex = "0123456789abcdef";
  let out = "";
  for (let i = 0; i < 32; i++) {
    const n =
      i === 12 ? 4 : i === 16 ? (Math.random() * 4) | 8 : (Math.random() * 16) | 0;
    out += hex[n];
    if (i === 7 || i === 11 || i === 15 || i === 19) out += "-";
  }
  return out;
}

async function readAll(): Promise<StockCountDraft[]> {
  const raw = await AsyncStorage.getItem(STOCK_COUNT_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as StockCountDraft[]) : [];
  } catch {
    // Corrupt payload — drop it rather than crash the screen on load.
    return [];
  }
}

async function writeAll(drafts: StockCountDraft[]): Promise<void> {
  await AsyncStorage.setItem(STOCK_COUNT_STORAGE_KEY, JSON.stringify(drafts));
}

// ── Public API ────────────────────────────────────────────────────────

export async function listStockCountDrafts(): Promise<StockCountDraft[]> {
  const drafts = await readAll();
  // Most-recently-updated first — matches the inventory screen's UX.
  return drafts.sort((a, b) =>
    (b.updatedAt || "").localeCompare(a.updatedAt || ""),
  );
}

export async function getCurrentDraft(): Promise<StockCountDraft | null> {
  const drafts = await listStockCountDrafts();
  return drafts.find((d) => d.status === "draft") ?? null;
}

export async function getDraftById(
  id: string,
): Promise<StockCountDraft | null> {
  const drafts = await readAll();
  return drafts.find((d) => d.id === id) ?? null;
}

export async function createDraftStockCount(params: {
  orgId: string;
  warehouseId: string;
}): Promise<StockCountDraft> {
  const now = new Date().toISOString();
  const draft: StockCountDraft = {
    id: uid(),
    orgId: params.orgId,
    warehouseId: params.warehouseId,
    sessionId: uid(),
    createdAt: now,
    updatedAt: now,
    status: "draft",
    items: [],
  };
  const drafts = await readAll();
  drafts.push(draft);
  await writeAll(drafts);
  return draft;
}

export async function saveDraft(draft: StockCountDraft): Promise<void> {
  const drafts = await readAll();
  const idx = drafts.findIndex((d) => d.id === draft.id);
  draft.updatedAt = new Date().toISOString();
  if (idx === -1) drafts.push(draft);
  else drafts[idx] = draft;
  await writeAll(drafts);
}

export async function addOrUpdateCountItem(
  draftId: string,
  item: Omit<StockCountItem, "id"> & { id?: string },
): Promise<StockCountDraft | null> {
  const drafts = await readAll();
  const draft = drafts.find((d) => d.id === draftId);
  if (!draft) return null;

  // Match by productId (+ optional batchId) so scanning the same
  // product twice updates the counted_qty instead of duplicating rows.
  const existing = draft.items.find(
    (i) =>
      i.productId === item.productId &&
      (i.batchId ?? null) === (item.batchId ?? null),
  );
  if (existing) {
    Object.assign(existing, item);
  } else {
    draft.items.push({ ...item, id: item.id ?? uid() });
  }
  draft.updatedAt = new Date().toISOString();
  await writeAll(drafts);
  return draft;
}

export async function removeCountItem(
  draftId: string,
  itemId: string,
): Promise<StockCountDraft | null> {
  const drafts = await readAll();
  const draft = drafts.find((d) => d.id === draftId);
  if (!draft) return null;
  draft.items = draft.items.filter((i) => i.id !== itemId);
  draft.updatedAt = new Date().toISOString();
  await writeAll(drafts);
  return draft;
}

export async function deleteDraft(draftId: string): Promise<void> {
  const drafts = await readAll();
  await writeAll(drafts.filter((d) => d.id !== draftId));
}

async function setStatus(
  draftId: string,
  status: StockCountStatus,
  patch?: Partial<StockCountDraft>,
): Promise<StockCountDraft | null> {
  const drafts = await readAll();
  const draft = drafts.find((d) => d.id === draftId);
  if (!draft) return null;
  draft.status = status;
  draft.updatedAt = new Date().toISOString();
  if (patch) Object.assign(draft, patch);
  await writeAll(drafts);
  return draft;
}

export function markDraftSubmitted(draftId: string) {
  return setStatus(draftId, "submitted", { lastError: undefined });
}

export function markDraftSynced(draftId: string) {
  return setStatus(draftId, "synced", { lastError: undefined });
}

export function markDraftFailed(draftId: string, error: string) {
  return setStatus(draftId, "failed", { lastError: error });
}

// Exposed for unit tests to reset local state.
export async function _resetAllStockCountsForTests(): Promise<void> {
  await AsyncStorage.removeItem(STOCK_COUNT_STORAGE_KEY);
}
