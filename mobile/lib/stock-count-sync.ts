// File: mobile/lib/stock-count-sync.ts
// Purpose: Upload submitted-but-unsynced stock count drafts to the
//          backend and call /submit + /sync. Reattempts on reconnect.
// Used by: StockCountSheet, inventory.tsx (reconnect listener)
//
// Online-detection strategy: no @react-native-community/netinfo
// dependency is added for Item 14. Instead the caller decides when to
// try a sync — typically after the user taps Submit, on app foreground,
// or after a manual retry. Any `fetch` network error flips the draft to
// status="failed" so the UI can show a "Will retry when online again"
// chip and the sweep runs again next time `processPendingStockCounts`
// is invoked.
//
// The backend router accepts client-supplied row UUIDs and upserts, so
// retried submissions are idempotent — the worst case after a flaky
// network is a duplicate HTTP round-trip, never duplicate adjustments.

import { apiClient, ApiError } from "./api-client";
import {
  listStockCountDrafts,
  markDraftFailed,
  markDraftSubmitted,
  markDraftSynced,
  type StockCountDraft,
} from "./stock-count";

export interface SyncOutcome {
  draftId: string;
  ok: boolean;
  error?: string;
}

type Listener = (outcome: SyncOutcome) => void;
const listeners = new Set<Listener>();

export function subscribeToReconnect(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(outcome: SyncOutcome) {
  for (const l of listeners) {
    try { l(outcome); } catch { /* listener errors must not break sweep */ }
  }
}

function payloadForDraft(d: StockCountDraft) {
  return {
    id: d.id,
    warehouse_id: d.warehouseId,
    items: d.items.map((i) => ({
      id: i.id,
      product_id: i.productId,
      batch_id: i.batchId ?? null,
      expected_qty: i.expectedQty,
      counted_qty: i.countedQty,
      note: i.note ?? null,
    })),
  };
}

/** Send a single draft through create → submit → sync. */
export async function queueStockCountSync(
  draft: StockCountDraft,
): Promise<SyncOutcome> {
  try {
    await apiClient.post(`/api/stock-counts`, payloadForDraft(draft));
    await apiClient.post(`/api/stock-counts/${draft.id}/submit`, {});
    await markDraftSubmitted(draft.id);
    await apiClient.post(`/api/stock-counts/${draft.id}/sync`, {});
    await markDraftSynced(draft.id);
    const outcome: SyncOutcome = { draftId: draft.id, ok: true };
    emit(outcome);
    return outcome;
  } catch (err) {
    const message =
      err instanceof ApiError
        ? `HTTP ${err.status}: ${err.message}`
        : err instanceof Error
          ? err.message
          : "Unknown error";
    await markDraftFailed(draft.id, message);
    const outcome: SyncOutcome = { draftId: draft.id, ok: false, error: message };
    emit(outcome);
    return outcome;
  }
}

/**
 * Walk every draft that is NOT yet fully synced and try to push it.
 * Safe to call repeatedly — already-synced rows are skipped.
 */
export async function processPendingStockCounts(): Promise<SyncOutcome[]> {
  const drafts = await listStockCountDrafts();
  const pending = drafts.filter(
    (d) => d.status === "submitted" || d.status === "failed",
  );
  const out: SyncOutcome[] = [];
  for (const d of pending) {
    out.push(await queueStockCountSync(d));
  }
  return out;
}

export function resetReconnectListenersForTests() {
  listeners.clear();
}
