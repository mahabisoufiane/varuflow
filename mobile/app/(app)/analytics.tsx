// File: mobile/app/(app)/analytics.tsx
// Purpose: Revenue & top-products analytics screen with period selector
// Used by: bottom tab navigator

import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { apiClient } from "@/lib/api-client";
import { Card }      from "@/components/ui/Card";

type Period = "7d" | "30d" | "90d";

const PERIODS: { key: Period; label: string }[] = [
  { key: "7d",  label: "7 days"  },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
];

interface AnalyticsSummary {
  revenue:         number;
  revenue_prev:    number;
  orders:          number;
  avg_order:       number;
  top_products:    TopProduct[];
  top_customers:   TopCustomer[];
}

interface TopProduct {
  id:       string;
  name:     string;
  units:    number;
  revenue:  number;
}

interface TopCustomer {
  id:       string;
  name:     string;
  invoices: number;
  total:    number;
}

function pct(curr: number, prev: number): string {
  if (!prev) return "";
  const d = ((curr - prev) / prev) * 100;
  return `${d >= 0 ? "+" : ""}${d.toFixed(1)}%`;
}

export default function AnalyticsScreen() {
  const [period,     setPeriod]     = useState<Period>("30d");
  const [data,       setData]       = useState<AnalyticsSummary | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,      setError]      = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const d = await apiClient.get<AnalyticsSummary>(`/api/analytics/summary?period=${period}`);
      setData(d);
    } catch {
      setError("Could not load analytics. Pull down to retry.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const change     = data ? pct(data.revenue, data.revenue_prev) : "";
  const changeUp   = change.startsWith("+");

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); load(true); }}
            tintColor="#6366F1"
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Analytics</Text>
        </View>

        {/* Period pills */}
        <View style={styles.periodRow}>
          {PERIODS.map((p) => (
            <Pressable
              key={p.key}
              style={[styles.pill, period === p.key && styles.pillActive]}
              onPress={() => setPeriod(p.key)}
            >
              <Text style={[styles.pillText, period === p.key && styles.pillTextActive]}>
                {p.label}
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
            <Pressable style={styles.retryBtn} onPress={() => load()}>
              <Text style={styles.retryText}>Retry</Text>
            </Pressable>
          </View>
        ) : data ? (
          <>
            {/* Revenue card */}
            <Card style={styles.revenueCard}>
              <Text style={styles.revenueLabel}>Total Revenue</Text>
              <Text style={styles.revenueValue}>
                {(data.revenue / 1000).toFixed(1)}k{" "}
                <Text style={styles.revenueCurrency}>SEK</Text>
              </Text>
              {change ? (
                <Text style={[styles.revenueChange, changeUp ? styles.up : styles.down]}>
                  {change} vs prev period
                </Text>
              ) : null}
            </Card>

            {/* Secondary KPIs */}
            <View style={styles.kpiRow}>
              <View style={styles.kpiCard}>
                <Text style={styles.kpiEmoji}>🛒</Text>
                <Text style={styles.kpiVal}>{data.orders}</Text>
                <Text style={styles.kpiLbl}>Orders</Text>
              </View>
              <View style={styles.kpiCard}>
                <Text style={styles.kpiEmoji}>📊</Text>
                <Text style={styles.kpiVal}>{(data.avg_order / 1000).toFixed(1)}k</Text>
                <Text style={styles.kpiLbl}>Avg order (SEK)</Text>
              </View>
            </View>

            {/* Top products */}
            <Card title="Top Products" style={styles.listCard}>
              {data.top_products.length === 0 ? (
                <Text style={styles.emptyText}>No data yet</Text>
              ) : (
                data.top_products.map((p, idx) => (
                  <View key={p.id} style={styles.rankRow}>
                    <Text style={styles.rank}>#{idx + 1}</Text>
                    <View style={styles.rankInfo}>
                      <Text style={styles.rankName}>{p.name}</Text>
                      <Text style={styles.rankSub}>{p.units} units</Text>
                    </View>
                    <Text style={styles.rankValue}>{(p.revenue / 1000).toFixed(1)}k</Text>
                  </View>
                ))
              )}
            </Card>

            {/* Top customers */}
            <Card title="Top Customers" style={styles.listCard}>
              {data.top_customers.length === 0 ? (
                <Text style={styles.emptyText}>No data yet</Text>
              ) : (
                data.top_customers.map((c, idx) => (
                  <View key={c.id} style={styles.rankRow}>
                    <Text style={styles.rank}>#{idx + 1}</Text>
                    <View style={styles.rankInfo}>
                      <Text style={styles.rankName}>{c.name}</Text>
                      <Text style={styles.rankSub}>{c.invoices} invoices</Text>
                    </View>
                    <Text style={styles.rankValue}>{(c.total / 1000).toFixed(1)}k</Text>
                  </View>
                ))
              )}
            </Card>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: "#0F172A" },
  scroll:        { padding: 20, paddingBottom: 40 },
  header:        { marginBottom: 16 },
  title:         { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  periodRow:     { flexDirection: "row", gap: 8, marginBottom: 16 },
  pill:          {
    paddingHorizontal: 14, paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.05)",
    borderWidth: 1, borderColor: "rgba(255,255,255,0.08)",
  },
  pillActive:    { backgroundColor: "rgba(99,102,241,0.15)", borderColor: "rgba(99,102,241,0.4)" },
  pillText:      { fontSize: 13, color: "#64748B", fontWeight: "500" },
  pillTextActive:{ color: "#818CF8" },
  center:        { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  errorText:     { fontSize: 14, color: "#94A3B8", textAlign: "center", marginBottom: 16 },
  retryBtn:      { paddingHorizontal: 20, paddingVertical: 8, backgroundColor: "rgba(99,102,241,0.15)", borderRadius: 8, borderWidth: 1, borderColor: "rgba(99,102,241,0.35)" },
  retryText:     { fontSize: 13, color: "#818CF8", fontWeight: "600" },
  revenueCard:   { marginBottom: 12 },
  revenueLabel:  { fontSize: 12, color: "#64748B", marginBottom: 6 },
  revenueValue:  { fontSize: 36, fontWeight: "800", color: "#F8FAFC" },
  revenueCurrency:{ fontSize: 18, fontWeight: "400", color: "#94A3B8" },
  revenueChange: { fontSize: 13, fontWeight: "600", marginTop: 6 },
  up:            { color: "#22C55E" },
  down:          { color: "#EF4444" },
  kpiRow:        { flexDirection: "row", gap: 12, marginBottom: 12 },
  kpiCard:       {
    flex: 1,
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius: 14,
    borderWidth: 1, borderColor: "rgba(255,255,255,0.07)",
    padding: 14,
  },
  kpiEmoji:      { fontSize: 18, marginBottom: 6 },
  kpiVal:        { fontSize: 20, fontWeight: "700", color: "#F8FAFC" },
  kpiLbl:        { fontSize: 11, color: "#64748B", marginTop: 2 },
  listCard:      { marginBottom: 12 },
  rankRow:       {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: "rgba(255,255,255,0.05)",
  },
  rank:          { fontSize: 13, fontWeight: "700", color: "#6366F1", width: 28 },
  rankInfo:      { flex: 1 },
  rankName:      { fontSize: 13, fontWeight: "600", color: "#F1F5F9" },
  rankSub:       { fontSize: 11, color: "#64748B", marginTop: 1 },
  rankValue:     { fontSize: 14, fontWeight: "700", color: "#F8FAFC" },
  emptyText:     { fontSize: 13, color: "#475569", textAlign: "center", paddingVertical: 10 },
});
