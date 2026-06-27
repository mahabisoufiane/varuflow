// File: mobile/components/StockCountRow.tsx
// Purpose: Single counted-item row rendered inside StockCountSheet
// Used by: StockCountSheet

import React from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { StockCountItem } from "@/lib/stock-count";

interface Props {
  item: StockCountItem;
  onChangeCounted: (qty: number) => void;
  onRemove: () => void;
}

export function StockCountRow({ item, onChangeCounted, onRemove }: Props) {
  const variance = item.countedQty - item.expectedQty;
  const varianceColor =
    variance === 0 ? "#64748B" : variance > 0 ? "#22C55E" : "#EF4444";

  return (
    <View style={styles.row} testID={`stock-count-row-${item.productId}`}>
      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={1}>
          {item.productName}
        </Text>
        <Text style={styles.meta}>
          Expected {item.expectedQty}  ·  Variance{" "}
          <Text style={{ color: varianceColor, fontWeight: "700" }}>
            {variance > 0 ? `+${variance}` : variance}
          </Text>
        </Text>
      </View>
      <TextInput
        testID={`stock-count-input-${item.productId}`}
        style={styles.input}
        value={String(item.countedQty)}
        keyboardType="number-pad"
        onChangeText={(raw) => {
          const n = parseInt(raw.replace(/[^0-9]/g, ""), 10);
          onChangeCounted(Number.isFinite(n) ? n : 0);
        }}
        selectTextOnFocus
      />
      <Pressable
        onPress={onRemove}
        hitSlop={10}
        accessibilityLabel="Remove row"
      >
        <Text style={styles.remove}>✕</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.04)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    gap: 10,
    marginBottom: 8,
  },
  info:   { flex: 1 },
  name:   { fontSize: 14, fontWeight: "600", color: "#F8FAFC" },
  meta:   { fontSize: 11, color: "#94A3B8", marginTop: 2 },
  input:  {
    width: 64,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(99,102,241,0.5)",
    backgroundColor: "rgba(99,102,241,0.1)",
    color: "#F8FAFC",
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
  remove: { fontSize: 16, color: "#475569", paddingHorizontal: 4 },
});

export default StockCountRow;
