// File: mobile/components/app/StockCard.tsx
// Purpose: Single product stock level card with status indicator and quick-action button
// Used by: inventory screen, dashboard screen

import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

export interface StockItem {
  id:          string;
  name:        string;
  sku:         string;
  qty:         number;
  reorderAt:   number;
  unit:        string;
  price?:      number;
  category?:   string;
}

interface StockCardProps {
  item:       StockItem;
  onPress?:   (item: StockItem) => void;
  onReorder?: (item: StockItem) => void;
}

function getStockStatus(qty: number, reorderAt: number): "ok" | "low" | "critical" {
  if (qty <= 0)             return "critical";
  if (qty <= reorderAt)     return "low";
  return "ok";
}

const STATUS_COLORS = {
  ok:       { dot: "#22C55E", label: "In stock",   bg: "rgba(34,197,94,0.08)"   },
  low:      { dot: "#F59E0B", label: "Low stock",  bg: "rgba(245,158,11,0.08)"  },
  critical: { dot: "#EF4444", label: "Out of stock", bg: "rgba(239,68,68,0.08)" },
};

export function StockCard({ item, onPress, onReorder }: StockCardProps) {
  const status = getStockStatus(item.qty, item.reorderAt);
  const sc     = STATUS_COLORS[status];

  return (
    <Pressable
      style={[styles.card, { backgroundColor: sc.bg }]}
      onPress={() => onPress?.(item)}
    >
      <View style={styles.row}>
        <View style={styles.info}>
          <View style={styles.nameRow}>
            <View style={[styles.dot, { backgroundColor: sc.dot }]} />
            <Text style={styles.name} numberOfLines={1}>{item.name}</Text>
          </View>
          <Text style={styles.sku}>{item.sku}</Text>
          {item.category && <Text style={styles.category}>{item.category}</Text>}
        </View>

        <View style={styles.qtyBlock}>
          <Text style={styles.qty}>{item.qty}</Text>
          <Text style={styles.unit}>{item.unit}</Text>
        </View>
      </View>

      <View style={styles.footer}>
        <View style={[styles.badge, { borderColor: sc.dot + "60" }]}>
          <Text style={[styles.badgeText, { color: sc.dot }]}>{sc.label}</Text>
        </View>
        {(status === "low" || status === "critical") && onReorder && (
          <Pressable
            style={styles.reorderBtn}
            onPress={(e) => { e.stopPropagation?.(); onReorder(item); }}
            hitSlop={6}
          >
            <Text style={styles.reorderText}>Reorder</Text>
          </Pressable>
        )}
        {item.price !== undefined && (
          <Text style={styles.price}>{item.price.toFixed(2)} kr</Text>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card:       {
    borderRadius:    14,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.08)",
    padding:         14,
    marginBottom:    10,
  },
  row:        { flexDirection: "row", alignItems: "flex-start" },
  info:       { flex: 1 },
  nameRow:    { flexDirection: "row", alignItems: "center", gap: 6 },
  dot:        { width: 7, height: 7, borderRadius: 4 },
  name:       { fontSize: 14, fontWeight: "600", color: "#F1F5F9", flex: 1 },
  sku:        { fontSize: 11, color: "#64748B", marginTop: 2, marginLeft: 13 },
  category:   { fontSize: 11, color: "#475569", marginTop: 1, marginLeft: 13 },
  qtyBlock:   { alignItems: "flex-end", minWidth: 52 },
  qty:        { fontSize: 22, fontWeight: "700", color: "#F8FAFC", lineHeight: 26 },
  unit:       { fontSize: 11, color: "#64748B" },
  footer:     { flexDirection: "row", alignItems: "center", marginTop: 10, gap: 8 },
  badge:      {
    borderWidth:  1,
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical:   2,
  },
  badgeText:  { fontSize: 11, fontWeight: "500" },
  reorderBtn: {
    backgroundColor: "rgba(99,102,241,0.15)",
    borderRadius:     6,
    paddingHorizontal: 10,
    paddingVertical:   3,
    borderWidth:      1,
    borderColor:      "rgba(99,102,241,0.35)",
  },
  reorderText: { fontSize: 11, color: "#818CF8", fontWeight: "600" },
  price:      { fontSize: 12, color: "#94A3B8", marginLeft: "auto" },
});
