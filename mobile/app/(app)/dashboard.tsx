// File: mobile/app/(app)/dashboard.tsx
// Purpose: Home dashboard — KPI cards, low-stock alert, recent activity
// Used by: bottom tab navigator

import React, { useState } from "react";
import {
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { apiClient }        from "@/lib/api-client";
import { useApiCall }       from "@/lib/use-api-call";
import { supabase }         from "@/lib/supabase";
import { Card }             from "@/components/ui/Card";
import { LowStockAlert }    from "@/components/app/LowStockAlert";
import type { StockItem }   from "@/components/app/StockCard";

interface DashboardSummary {
  revenue:        number;
  open_invoices:  number;
  total_products: number;
}

interface KPI {
  label:  string;
  value:  string;
  change: string;
  up:     boolean;
  emoji:  string;
}

export default function DashboardScreen() {
  const [userName, setUserName] = useState("there");

  // Load user name once (non-critical, no error handling needed)
  React.useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      const name = user?.user_metadata?.full_name;
      if (name) setUserName(name.split(" ")[0]);
    });
  }, []);

  const {
    data: summary,
    loading: sumLoading,
    refreshing,
    error: sumError,
    refresh,
  } = useApiCall(() =>
    apiClient.get<DashboardSummary>("/api/analytics/summary"),
  );

  const {
    data: lowStock,
    loading: stockLoading,
  } = useApiCall(() =>
    apiClient.get<StockItem[]>("/api/inventory/low-stock"),
  );

  const loading = sumLoading || stockLoading;

  const kpis: KPI[] = summary
    ? [
        { label: "Revenue (MTD)",  value: `${(summary.revenue / 1000).toFixed(1)}k kr`, change: "+12%", up: true,  emoji: "💰" },
        { label: "Open Invoices",  value: String(summary.open_invoices),                 change: "-3",   up: false, emoji: "🧾" },
        { label: "Products",       value: String(summary.total_products),                change: "",     up: true,  emoji: "📦" },
        { label: "Low Stock",      value: String((lowStock ?? []).length),               change: "",     up: false, emoji: "⚠️" },
      ]
    : [];

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor="#6366F1" />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.greeting}>Hello, {userName} 👋</Text>
          <Text style={styles.date}>
            {new Date().toLocaleDateString("en-SE", {
              weekday: "long", month: "long", day: "numeric",
            })}
          </Text>
        </View>

        {/* Error */}
        {sumError && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>{sumError}</Text>
          </View>
        )}

        {/* KPI grid */}
        <View style={styles.kpiGrid}>
          {loading
            ? [0, 1, 2, 3].map((i) => <View key={i} style={[styles.kpiCard, styles.kpiSkeleton]} />)
            : kpis.map((k) => (
                <View key={k.label} style={styles.kpiCard}>
                  <Text style={styles.kpiEmoji}>{k.emoji}</Text>
                  <Text style={styles.kpiValue}>{k.value}</Text>
                  <Text style={styles.kpiLabel}>{k.label}</Text>
                  {k.change ? (
                    <Text style={[styles.kpiChange, k.up ? styles.changeUp : styles.changeDown]}>
                      {k.change}
                    </Text>
                  ) : null}
                </View>
              ))}
        </View>

        {/* Low stock alert */}
        {(lowStock ?? []).length > 0 && (
          <LowStockAlert items={lowStock!} />
        )}

        {/* Recent activity placeholder */}
        <Card title="Recent Activity" style={styles.activityCard}>
          <Text style={styles.emptyText}>Pull to refresh for latest activity</Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: "#0F172A" },
  scroll:      { padding: 20, paddingBottom: 40 },
  header:      { marginBottom: 20 },
  greeting:    { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  date:        { fontSize: 13, color: "#64748B", marginTop: 2 },
  errorBanner: {
    backgroundColor: "rgba(239,68,68,0.10)", borderRadius: 10, padding: 12,
    marginBottom: 16, borderWidth: 1, borderColor: "rgba(239,68,68,0.3)",
  },
  errorText:   { fontSize: 13, color: "#FCA5A5" },
  kpiGrid:     { flexDirection: "row", flexWrap: "wrap", gap: 12, marginBottom: 16 },
  kpiCard:     {
    flex: 1, minWidth: "45%",
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius: 14, borderWidth: 1, borderColor: "rgba(255,255,255,0.07)", padding: 14,
  },
  kpiSkeleton: { height: 90, opacity: 0.4 },
  kpiEmoji:    { fontSize: 20, marginBottom: 8 },
  kpiValue:    { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  kpiLabel:    { fontSize: 11, color: "#64748B", marginTop: 2 },
  kpiChange:   { fontSize: 11, fontWeight: "600", marginTop: 4 },
  changeUp:    { color: "#22C55E" },
  changeDown:  { color: "#EF4444" },
  activityCard:{ marginBottom: 16 },
  emptyText:   { fontSize: 13, color: "#475569", textAlign: "center", paddingVertical: 8 },
});
