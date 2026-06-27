// File: mobile/app/(app)/inventory.tsx
// Purpose: Full inventory list with search, filter by status, pull-to-refresh
// Used by: bottom tab navigator

import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { apiClient }         from "@/lib/api-client";
import { useApiCall }        from "@/lib/use-api-call";
import { StockCard }         from "@/components/app/StockCard";
import type { StockItem }    from "@/components/app/StockCard";
import BarcodeScanner        from "@/components/app/BarcodeScanner";
import { useDeviceLayout }   from "@/lib/useDeviceLayout";
import { TabletGrid }        from "@/components/TabletGrid";
import TabletTopBar          from "@/components/TabletTopBar";
import StockCountSheet       from "@/components/StockCountSheet";
import { tStockCount }       from "@/lib/stock-count-i18n";
import {
  createDraftStockCount,
  getCurrentDraft,
  listStockCountDrafts,
  type StockCountDraft,
} from "@/lib/stock-count";
import { processPendingStockCounts } from "@/lib/stock-count-sync";

type Filter = "all" | "low" | "critical";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all",      label: "All"       },
  { key: "low",      label: "Low Stock" },
  { key: "critical", label: "Out"       },
];

export default function InventoryScreen() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [scannerOpen, setScannerOpen] = useState(false);
  const { isTablet } = useDeviceLayout();

  // ── Item 14: stock-count state ──────────────────────────────────────
  const [countSheetOpen, setCountSheetOpen] = useState(false);
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);
  const [draftCount, setDraftCount] = useState<StockCountDraft | null>(null);
  const [draftList, setDraftList] = useState<StockCountDraft[]>([]);

  const refreshDrafts = React.useCallback(async () => {
    const [current, all] = await Promise.all([
      getCurrentDraft(),
      listStockCountDrafts(),
    ]);
    setDraftCount(current);
    setDraftList(all);
  }, []);

  useEffect(() => {
    void refreshDrafts();
    // Best-effort reconnect sweep — pushes any failed drafts through the
    // queue when the screen mounts (e.g. after returning from offline).
    void processPendingStockCounts().then(refreshDrafts);
  }, [refreshDrafts]);

  async function handleStartOrResumeCount() {
    const existing = await getCurrentDraft();
    if (existing) {
      setActiveDraftId(existing.id);
      setCountSheetOpen(true);
      return;
    }
    const created = await createDraftStockCount({
      orgId: "", // server fills from auth context
      warehouseId: "",
    });
    setActiveDraftId(created.id);
    setCountSheetOpen(true);
    await refreshDrafts();
  }

  const { data: items, loading, refreshing, error, reload, refresh } = useApiCall(
    () => apiClient.get<StockItem[]>("/api/inventory/products"),
  );

  // Cheap toast stand-in — Alert is everywhere on iOS/Android without
  // pulling in a 3rd-party snackbar just for the scanner feedback.
  function toast(message: string) {
    Alert.alert("Varuflow", message);
  }

  const displayed = useMemo(() => {
    let list = items ?? [];
    if (filter === "critical") list = list.filter((i) => i.qty <= 0);
    if (filter === "low")      list = list.filter((i) => i.qty > 0 && i.qty <= i.reorderAt);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.sku.toLowerCase().includes(q)  ||
          (i.category ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [items, filter, search]);

  // ── Tablet branch (Item 13) ──────────────────────────────────────────
  // Uses the virtualised TabletGrid so hundreds of products render
  // smoothly. Phone branch below is unchanged.
  if (isTablet) {
    return (
      <SafeAreaView style={styles.safe} testID="inventory-tablet">
        <TabletTopBar
          title="Inventory"
          subtitle={`${displayed.length} of ${(items ?? []).length} products`}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search by name, SKU, or category…"
          actionLabel="📷  Scan"
          onAction={() => setScannerOpen(true)}
        />
        <StockCountBar
          draftCount={draftCount}
          draftList={draftList}
          onStart={handleStartOrResumeCount}
        />
        <StockCountSheet
          visible={countSheetOpen}
          draftId={activeDraftId}
          onClose={() => {
            setCountSheetOpen(false);
            void refreshDrafts();
          }}
          onSynced={() => {
            void refreshDrafts();
            refresh();
          }}
        />
        <BarcodeScanner
          visible={scannerOpen}
          onClose={() => { setScannerOpen(false); refresh(); }}
          toast={(msg) => toast(msg)}
        />
        <View style={styles.filterRow}>
          {FILTERS.map((f) => (
            <Pressable
              key={f.key}
              style={[styles.pill, filter === f.key && styles.pillActive]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[styles.pillText, filter === f.key && styles.pillTextActive]}>
                {f.label}
              </Text>
            </Pressable>
          ))}
        </View>
        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color="#6366F1" size="large" />
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable style={styles.retryBtn} onPress={reload}>
              <Text style={styles.retryText}>Retry</Text>
            </Pressable>
          </View>
        ) : (
          <TabletGrid
            data={displayed}
            keyExtractor={(i) => String((i as StockItem).id)}
            refreshing={refreshing}
            onRefresh={refresh}
            renderItem={(item) => <StockCard item={item as StockItem} />}
            ListEmptyComponent={
              <Text style={styles.emptyText}>
                {search ? "No products match your search." : "No products in this category."}
              </Text>
            }
          />
        )}
      </SafeAreaView>
    );
  }

  // ── Phone branch (unchanged) ─────────────────────────────────────────
  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Inventory</Text>
        <Text style={styles.count}>{(items ?? []).length} products</Text>
      </View>

      {/* Scan button */}
      <Pressable
        style={styles.scanBtn}
        onPress={() => setScannerOpen(true)}
        accessibilityLabel="Skanna produkt"
      >
        <Text style={styles.scanBtnText}>📷  Skanna produkt</Text>
      </Pressable>

      {/* Item 14 — Stock count quick-action bar */}
      <StockCountBar
        draftCount={draftCount}
        draftList={draftList}
        onStart={handleStartOrResumeCount}
      />
      <StockCountSheet
        visible={countSheetOpen}
        draftId={activeDraftId}
        onClose={() => {
          setCountSheetOpen(false);
          void refreshDrafts();
        }}
        onSynced={() => {
          void refreshDrafts();
          refresh();
        }}
      />

      <BarcodeScanner
        visible={scannerOpen}
        onClose={() => {
          setScannerOpen(false);
          refresh();
        }}
        toast={(msg) => toast(msg)}
      />

      {/* Search */}
      <View style={styles.searchWrap}>
        <Text style={styles.searchIcon}>🔍</Text>
        <TextInput
          style={styles.search}
          placeholder="Search by name, SKU, or category…"
          placeholderTextColor="#475569"
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
          returnKeyType="search"
        />
        {search.length > 0 && (
          <Pressable onPress={() => setSearch("")} hitSlop={8}>
            <Text style={styles.clearSearch}>✕</Text>
          </Pressable>
        )}
      </View>

      {/* Filter pills */}
      <View style={styles.filterRow}>
        {FILTERS.map((f) => (
          <Pressable
            key={f.key}
            style={[styles.pill, filter === f.key && styles.pillActive]}
            onPress={() => setFilter(f.key)}
          >
            <Text style={[styles.pillText, filter === f.key && styles.pillTextActive]}>
              {f.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* List */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color="#6366F1" size="large" />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.retryBtn} onPress={reload}>
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={refresh}
              tintColor="#6366F1"
            />
          }
        >
          {displayed.length === 0 ? (
            <Text style={styles.emptyText}>
              {search ? "No products match your search." : "No products in this category."}
            </Text>
          ) : (
            displayed.map((item) => (
              <StockCard key={item.id} item={item} />
            ))
          )}
          <View style={{ height: 24 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: "#0F172A" },
  header:        {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 20, paddingTop: 20, paddingBottom: 12,
  },
  title:         { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  count:         { fontSize: 13, color: "#64748B" },
  searchWrap:    {
    flexDirection: "row", alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.05)",
    borderRadius: 12, borderWidth: 1, borderColor: "rgba(255,255,255,0.08)",
    marginHorizontal: 20, paddingHorizontal: 12, height: 44, marginBottom: 12,
  },
  searchIcon:    { fontSize: 15, marginRight: 8 },
  search:        { flex: 1, fontSize: 14, color: "#F8FAFC" },
  clearSearch:   { fontSize: 14, color: "#475569", paddingLeft: 8 },
  filterRow:     { flexDirection: "row", paddingHorizontal: 20, gap: 8, marginBottom: 14 },
  pill:          {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.05)",
    borderWidth: 1, borderColor: "rgba(255,255,255,0.08)",
  },
  pillActive:    { backgroundColor: "rgba(99,102,241,0.15)", borderColor: "rgba(99,102,241,0.4)" },
  pillText:      { fontSize: 13, color: "#64748B", fontWeight: "500" },
  pillTextActive:{ color: "#818CF8" },
  list:          { paddingHorizontal: 20 },
  center:        { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  errorText:     { fontSize: 14, color: "#94A3B8", textAlign: "center", marginBottom: 16 },
  retryBtn:      {
    paddingHorizontal: 20, paddingVertical: 8,
    backgroundColor: "rgba(99,102,241,0.15)", borderRadius: 8,
    borderWidth: 1, borderColor: "rgba(99,102,241,0.35)",
  },
  retryText:     { fontSize: 13, color: "#818CF8", fontWeight: "600" },
  emptyText:     { textAlign: "center", color: "#475569", fontSize: 14, paddingVertical: 24 },
  scanBtn: {
    marginHorizontal: 20, marginBottom: 12,
    paddingVertical: 12, borderRadius: 12, alignItems: "center",
    backgroundColor: "rgba(99,102,241,0.20)",
    borderWidth: 1, borderColor: "rgba(99,102,241,0.45)",
  },
  scanBtnText: { color: "#F8FAFC", fontWeight: "700", fontSize: 14 },
});


// ── Item 14: Stock count quick-action bar ──────────────────────────────
// Rendered inside both tablet and phone branches. Surfaces the current
// draft (if any) with a "Resume" verb + a sync-status chip, or a
// primary "Start stock count" button when there's no open draft.
function StockCountBar({
  draftCount,
  draftList,
  onStart,
  lang,
}: {
  draftCount: StockCountDraft | null;
  draftList: StockCountDraft[];
  onStart: () => void;
  lang?: string;
}) {
  const submittedOrSynced = draftList.filter(
    (d) => d.status === "submitted" || d.status === "synced" || d.status === "failed",
  );
  return (
    <View testID="stock-count-bar" style={stockCountBarStyles.wrap}>
      <Pressable
        testID="stock-count-start"
        style={stockCountBarStyles.primary}
        onPress={onStart}
      >
        <Text style={stockCountBarStyles.primaryText}>
          {draftCount
            ? tStockCount(lang, "resume")
            : tStockCount(lang, "start")}
        </Text>
      </Pressable>
      {draftCount && (
        <View
          testID="stock-count-chip"
          style={[
            stockCountBarStyles.chip,
            { backgroundColor: chipBg(draftCount.status) },
          ]}
        >
          <Text style={stockCountBarStyles.chipText}>
            {tStockCount(lang, chipKey(draftCount.status))}
          </Text>
        </View>
      )}
      {submittedOrSynced.length > 0 && (
        <Text style={stockCountBarStyles.meta}>
          {submittedOrSynced.length} {tStockCount(lang, "sync_status")}
        </Text>
      )}
    </View>
  );
}

function chipBg(status: StockCountDraft["status"]): string {
  if (status === "synced")    return "rgba(34,197,94,0.18)";
  if (status === "failed")    return "rgba(239,68,68,0.18)";
  if (status === "submitted") return "rgba(245,158,11,0.18)";
  return "rgba(148,163,184,0.18)";
}

function chipKey(
  status: StockCountDraft["status"],
): "draft" | "pending_sync" | "synced" | "failed" {
  if (status === "synced")    return "synced";
  if (status === "failed")    return "failed";
  if (status === "submitted") return "pending_sync";
  return "draft";
}

const stockCountBarStyles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginHorizontal: 20,
    marginBottom: 12,
  },
  primary: {
    flex: 1,
    paddingVertical: 11,
    borderRadius: 12,
    alignItems: "center",
    backgroundColor: "rgba(34,197,94,0.18)",
    borderWidth: 1,
    borderColor: "rgba(34,197,94,0.45)",
  },
  primaryText: { color: "#86EFAC", fontSize: 13, fontWeight: "700" },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
  },
  chipText: { color: "#F8FAFC", fontSize: 11, fontWeight: "700" },
  meta: { color: "#64748B", fontSize: 11 },
});
