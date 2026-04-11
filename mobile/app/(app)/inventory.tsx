// File: mobile/app/(app)/inventory.tsx
// Purpose: Full inventory list with search, filter by status, pull-to-refresh
// Used by: bottom tab navigator

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
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
import { StockCard }         from "@/components/app/StockCard";
import type { StockItem }    from "@/components/app/StockCard";

type Filter = "all" | "low" | "critical";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all",      label: "All"       },
  { key: "low",      label: "Low Stock" },
  { key: "critical", label: "Out"       },
];

export default function InventoryScreen() {
  const [items,      setItems]      = useState<StockItem[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [search,     setSearch]     = useState("");
  const [filter,     setFilter]     = useState<Filter>("all");

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<StockItem[]>("/api/inventory/products");
      setItems(data);
    } catch {
      setError("Could not load inventory. Pull down to retry.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const displayed = useMemo(() => {
    let list = items;
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

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Inventory</Text>
        <Text style={styles.count}>{items.length} products</Text>
      </View>

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
          <Pressable style={styles.retryBtn} onPress={() => load()}>
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
              onRefresh={() => { setRefreshing(true); load(true); }}
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
    flexDirection:   "row",
    alignItems:      "center",
    justifyContent:  "space-between",
    paddingHorizontal: 20,
    paddingTop:      20,
    paddingBottom:   12,
  },
  title:         { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  count:         { fontSize: 13, color: "#64748B" },
  searchWrap:    {
    flexDirection:   "row",
    alignItems:      "center",
    backgroundColor: "rgba(255,255,255,0.05)",
    borderRadius:    12,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.08)",
    marginHorizontal: 20,
    paddingHorizontal: 12,
    height:          44,
    marginBottom:    12,
  },
  searchIcon:    { fontSize: 15, marginRight: 8 },
  search:        { flex: 1, fontSize: 14, color: "#F8FAFC" },
  clearSearch:   { fontSize: 14, color: "#475569", paddingLeft: 8 },
  filterRow:     {
    flexDirection:    "row",
    paddingHorizontal: 20,
    gap:              8,
    marginBottom:     14,
  },
  pill:          {
    paddingHorizontal: 14,
    paddingVertical:   6,
    borderRadius:      20,
    backgroundColor:   "rgba(255,255,255,0.05)",
    borderWidth:       1,
    borderColor:       "rgba(255,255,255,0.08)",
  },
  pillActive:    { backgroundColor: "rgba(99,102,241,0.15)", borderColor: "rgba(99,102,241,0.4)" },
  pillText:      { fontSize: 13, color: "#64748B", fontWeight: "500" },
  pillTextActive:{ color: "#818CF8" },
  list:          { paddingHorizontal: 20 },
  center:        { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  errorText:     { fontSize: 14, color: "#94A3B8", textAlign: "center", marginBottom: 16 },
  retryBtn:      {
    paddingHorizontal: 20,
    paddingVertical:   8,
    backgroundColor:   "rgba(99,102,241,0.15)",
    borderRadius:      8,
    borderWidth:       1,
    borderColor:       "rgba(99,102,241,0.35)",
  },
  retryText:     { fontSize: 13, color: "#818CF8", fontWeight: "600" },
  emptyText:     { textAlign: "center", color: "#475569", fontSize: 14, paddingVertical: 24 },
});
