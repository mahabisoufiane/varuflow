// File: mobile/app/(app)/dashboard.tsx
// Purpose: Home dashboard — KPI cards, low-stock alert, recent activity
// Used by: bottom tab navigator

import React, { useCallback, useEffect, useState } from "react";
import {
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { apiClient }        from "@/lib/api-client";
import { supabase }         from "@/lib/supabase";
import { Card }             from "@/components/ui/Card";
import { LowStockAlert }    from "@/components/app/LowStockAlert";
import type { StockItem }   from "@/components/app/StockCard";

interface KPI {
  label:  string;
  value:  string;
  change: string;
  up:     boolean;
  emoji:  string;
}

interface DashboardData {
  totalRevenue:    number;
  openInvoices:    number;
  totalProducts:   number;
  lowStockItems:   StockItem[];
  recentActivity:  ActivityItem[];
}

interface ActivityItem {
  id:        string;
  type:      "invoice" | "sync" | "order" | "alert";
  title:     string;
  subtitle:  string;
  time:      string;
}

const ACTIVITY_ICONS: Record<ActivityItem["type"], string> = {
  invoice: "🧾",
  sync:    "🔄",
  order:   "📦",
  alert:   "⚠️",
};

export default function DashboardScreen() {
  const [data,       setData]       = useState<DashboardData | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [userName,   setUserName]   = useState("there");

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (user?.user_metadata?.full_name) {
        setUserName(user.user_metadata.full_name.split(" ")[0]);
      }

      const [dash, stockList] = await Promise.all([
        apiClient.get<{ revenue: number; open_invoices: number; total_products: number }>(
          "/api/analytics/summary",
        ),
        apiClient.get<StockItem[]>("/api/inventory/low-stock"),
      ]);

      setData({
        totalRevenue:   dash.revenue,
        openInvoices:   dash.open_invoices,
        totalProducts:  dash.total_products,
        lowStockItems:  stockList,
        recentActivity: [],
      });
    } catch (e: unknown) {
      setError("Could not load dashboard. Pull to refresh.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const kpis: KPI[] = data
    ? [
        { label: "Revenue (MTD)",    value: `${(data.totalRevenue / 1000).toFixed(1)}k kr`, change: "+12%", up: true,  emoji: "💰" },
        { label: "Open Invoices",    value: String(data.openInvoices),                       change: "-3",   up: false, emoji: "🧾" },
        { label: "Products",         value: String(data.totalProducts),                      change: "",     up: true,  emoji: "📦" },
        { label: "Low Stock",        value: String(data.lowStockItems.length),               change: "",     up: false, emoji: "⚠️" },
      ]
    : [];

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
          <View>
            <Text style={styles.greeting}>Hello, {userName} 👋</Text>
            <Text style={styles.date}>{new Date().toLocaleDateString("en-SE", { weekday: "long", month: "long", day: "numeric" })}</Text>
          </View>
        </View>

        {/* Error */}
        {error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* KPI grid */}
        {loading ? (
          <View style={styles.kpiGrid}>
            {[0, 1, 2, 3].map((i) => (
              <View key={i} style={[styles.kpiCard, styles.kpiSkeleton]} />
            ))}
          </View>
        ) : (
          <View style={styles.kpiGrid}>
            {kpis.map((k) => (
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
        )}

        {/* Low stock alert */}
        {data && data.lowStockItems.length > 0 && (
          <LowStockAlert items={data.lowStockItems} />
        )}

        {/* Recent activity */}
        <Card title="Recent Activity" style={styles.activityCard}>
          {data && data.recentActivity.length > 0 ? (
            data.recentActivity.map((item) => (
              <View key={item.id} style={styles.activityRow}>
                <Text style={styles.activityIcon}>{ACTIVITY_ICONS[item.type]}</Text>
                <View style={styles.activityInfo}>
                  <Text style={styles.activityTitle}>{item.title}</Text>
                  <Text style={styles.activitySub}>{item.subtitle}</Text>
                </View>
                <Text style={styles.activityTime}>{item.time}</Text>
              </View>
            ))
          ) : (
            <Text style={styles.emptyText}>No recent activity</Text>
          )}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:           { flex: 1, backgroundColor: "#0F172A" },
  scroll:         { padding: 20, paddingBottom: 40 },
  header:         { marginBottom: 20 },
  greeting:       { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  date:           { fontSize: 13, color: "#64748B", marginTop: 2 },
  errorBanner:    {
    backgroundColor: "rgba(239,68,68,0.10)",
    borderRadius:    10,
    padding:         12,
    marginBottom:    16,
    borderWidth:     1,
    borderColor:     "rgba(239,68,68,0.3)",
  },
  errorText:      { fontSize: 13, color: "#FCA5A5" },
  kpiGrid:        { flexDirection: "row", flexWrap: "wrap", gap: 12, marginBottom: 16 },
  kpiCard:        {
    flex:            1,
    minWidth:        "45%",
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius:    14,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.07)",
    padding:         14,
  },
  kpiSkeleton:    { height: 90, opacity: 0.4 },
  kpiEmoji:       { fontSize: 20, marginBottom: 8 },
  kpiValue:       { fontSize: 22, fontWeight: "700", color: "#F8FAFC" },
  kpiLabel:       { fontSize: 11, color: "#64748B", marginTop: 2 },
  kpiChange:      { fontSize: 11, fontWeight: "600", marginTop: 4 },
  changeUp:       { color: "#22C55E" },
  changeDown:     { color: "#EF4444" },
  activityCard:   { marginBottom: 16 },
  activityRow:    {
    flexDirection: "row",
    alignItems:    "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.05)",
  },
  activityIcon:   { fontSize: 20, marginRight: 12 },
  activityInfo:   { flex: 1 },
  activityTitle:  { fontSize: 13, fontWeight: "600", color: "#F1F5F9" },
  activitySub:    { fontSize: 11, color: "#64748B", marginTop: 1 },
  activityTime:   { fontSize: 11, color: "#475569" },
  emptyText:      { fontSize: 13, color: "#475569", textAlign: "center", paddingVertical: 12 },
});
