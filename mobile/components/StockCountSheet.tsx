// File: mobile/components/StockCountSheet.tsx
// Purpose: Offline-first stock-count workflow UI (Item 14).
//          Phone: full-screen modal.
//          Tablet: two-pane split (scan/list on the left, summary on the right).
// Used by: mobile/app/(app)/inventory.tsx

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useDeviceLayout } from "@/lib/useDeviceLayout";
import { tStockCount } from "@/lib/stock-count-i18n";
import {
  addOrUpdateCountItem,
  deleteDraft,
  getDraftById,
  removeCountItem,
  saveDraft,
  type StockCountDraft,
  type StockCountItem,
} from "@/lib/stock-count";
import { queueStockCountSync } from "@/lib/stock-count-sync";
import { StockCountRow } from "./StockCountRow";

interface Props {
  visible: boolean;
  draftId: string | null;
  onClose: () => void;
  lang?: string;
  onSynced?: () => void;
}

export default function StockCountSheet({
  visible,
  draftId,
  onClose,
  lang,
  onSynced,
}: Props) {
  const { isTablet } = useDeviceLayout();
  const [draft, setDraft] = useState<StockCountDraft | null>(null);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!draftId) return;
    const d = await getDraftById(draftId);
    setDraft(d);
  }, [draftId]);

  useEffect(() => {
    if (visible) void reload();
  }, [visible, reload]);

  const variance = useMemo(() => {
    if (!draft) return { total: 0, positive: 0, negative: 0 };
    let positive = 0;
    let negative = 0;
    for (const i of draft.items) {
      const v = i.countedQty - i.expectedQty;
      if (v > 0) positive += v;
      if (v < 0) negative += v;
    }
    return { total: positive + negative, positive, negative };
  }, [draft]);

  async function handleUpdateQty(item: StockCountItem, qty: number) {
    if (!draft) return;
    const updated = await addOrUpdateCountItem(draft.id, {
      ...item,
      countedQty: qty,
    });
    setDraft(updated);
  }

  async function handleRemove(itemId: string) {
    if (!draft) return;
    const updated = await removeCountItem(draft.id, itemId);
    setDraft(updated);
  }

  async function handleAddByNameSearch(raw: string) {
    if (!draft) return;
    const trimmed = raw.trim();
    if (!trimmed) return;
    // Lightweight manual-entry: the sheet is primarily scanner-first,
    // but typing a SKU/name adds a placeholder row with expectedQty=0
    // that the user can correct against the paper list.
    const updated = await addOrUpdateCountItem(draft.id, {
      productId: `manual:${trimmed}`,
      productName: trimmed,
      expectedQty: 0,
      countedQty: 1,
    });
    setDraft(updated);
    setSearch("");
  }

  async function handleSubmit() {
    if (!draft || draft.items.length === 0) {
      Alert.alert("Empty count", "Add at least one counted item first.");
      return;
    }
    setBusy(true);
    // Mark submitted locally first so the draft survives the network
    // round-trip even if the user force-quits mid-submit.
    await saveDraft({ ...draft, status: "submitted" });
    const outcome = await queueStockCountSync({ ...draft, status: "submitted" });
    setBusy(false);
    if (outcome.ok) {
      Alert.alert("Varuflow", tStockCount(lang, "stock_count_synced"));
      onSynced?.();
      onClose();
    } else {
      Alert.alert(
        "Varuflow",
        `${tStockCount(lang, "failed")}: ${tStockCount(lang, "will_retry")}`,
      );
      await reload();
    }
  }

  async function handleCancel() {
    if (!draft) return;
    Alert.alert(
      tStockCount(lang, "cancel"),
      "Discard this stock count?",
      [
        { text: "Keep", style: "cancel" },
        {
          text: tStockCount(lang, "cancel"),
          style: "destructive",
          onPress: async () => {
            await deleteDraft(draft.id);
            onClose();
          },
        },
      ],
    );
  }

  if (!visible) return null;

  const content = (
    <View
      style={styles.container}
      testID={isTablet ? "stock-count-sheet-tablet" : "stock-count-sheet-phone"}
    >
      <View style={styles.header}>
        <Text style={styles.title}>{tStockCount(lang, "start")}</Text>
        <Pressable onPress={onClose} hitSlop={10}>
          <Text style={styles.closeBtn}>✕</Text>
        </Pressable>
      </View>

      <View style={styles.searchRow}>
        <TextInput
          style={styles.search}
          placeholder={tStockCount(lang, "scan_or_search")}
          placeholderTextColor="#64748B"
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={() => void handleAddByNameSearch(search)}
          returnKeyType="done"
          autoCapitalize="none"
          testID="stock-count-search"
        />
      </View>

      {isTablet ? (
        <View style={styles.split} testID="stock-count-split">
          <View style={styles.listPane}>
            <ItemList
              draft={draft}
              onUpdate={handleUpdateQty}
              onRemove={handleRemove}
            />
          </View>
          <View style={styles.summaryPane}>
            <Summary
              lang={lang}
              draft={draft}
              variance={variance}
              busy={busy}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
            />
          </View>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.phoneScroll}>
          <ItemList
            draft={draft}
            onUpdate={handleUpdateQty}
            onRemove={handleRemove}
          />
          <Summary
            lang={lang}
            draft={draft}
            variance={variance}
            busy={busy}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
          />
        </ScrollView>
      )}
    </View>
  );

  return (
    <Modal
      visible={visible}
      transparent={false}
      animationType="slide"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
      >
        {content}
      </KeyboardAvoidingView>
    </Modal>
  );
}

function ItemList({
  draft,
  onUpdate,
  onRemove,
}: {
  draft: StockCountDraft | null;
  onUpdate: (item: StockCountItem, qty: number) => void;
  onRemove: (itemId: string) => void;
}) {
  if (!draft) {
    return <Text style={styles.empty}>Loading…</Text>;
  }
  if (draft.items.length === 0) {
    return <Text style={styles.empty}>No items counted yet. Scan or search to begin.</Text>;
  }
  return (
    <View>
      {draft.items.map((item) => (
        <StockCountRow
          key={item.id}
          item={item}
          onChangeCounted={(qty) => onUpdate(item, qty)}
          onRemove={() => onRemove(item.id)}
        />
      ))}
    </View>
  );
}

function Summary({
  lang,
  draft,
  variance,
  busy,
  onSubmit,
  onCancel,
}: {
  lang?: string;
  draft: StockCountDraft | null;
  variance: { total: number; positive: number; negative: number };
  busy: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  return (
    <View style={styles.summary}>
      <Text style={styles.summaryTitle}>{tStockCount(lang, "variance")}</Text>
      <View style={styles.summaryRow}>
        <Text style={styles.summaryLabel}>+</Text>
        <Text style={[styles.summaryValue, { color: "#22C55E" }]}>
          {variance.positive}
        </Text>
      </View>
      <View style={styles.summaryRow}>
        <Text style={styles.summaryLabel}>−</Text>
        <Text style={[styles.summaryValue, { color: "#EF4444" }]}>
          {variance.negative}
        </Text>
      </View>
      <View style={styles.summaryRow}>
        <Text style={styles.summaryLabel}>
          {tStockCount(lang, "sync_status")}
        </Text>
        <Text style={styles.summaryValue}>{draft?.status ?? "draft"}</Text>
      </View>

      <Pressable
        style={[styles.submitBtn, busy && { opacity: 0.6 }]}
        disabled={busy}
        onPress={onSubmit}
        testID="stock-count-submit"
      >
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.submitText}>{tStockCount(lang, "submit")}</Text>
        )}
      </Pressable>
      <Pressable style={styles.cancelBtn} onPress={onCancel}>
        <Text style={styles.cancelText}>{tStockCount(lang, "cancel")}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 50,
    paddingBottom: 12,
  },
  title: { fontSize: 20, fontWeight: "700", color: "#F8FAFC" },
  closeBtn: { fontSize: 20, color: "#94A3B8", padding: 6 },
  searchRow: { paddingHorizontal: 20, paddingBottom: 10 },
  search: {
    backgroundColor: "rgba(255,255,255,0.05)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    paddingHorizontal: 14,
    height: 48,
    fontSize: 15,
    color: "#F8FAFC",
  },
  split: { flex: 1, flexDirection: "row", padding: 20, gap: 16 },
  listPane: { flex: 2 },
  summaryPane: { flex: 1 },
  phoneScroll: { padding: 20, paddingBottom: 60 },
  empty: {
    fontSize: 13,
    color: "#64748B",
    textAlign: "center",
    padding: 20,
  },
  summary: {
    marginTop: 16,
    padding: 16,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.04)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
  },
  summaryTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#94A3B8",
    letterSpacing: 0.5,
    textTransform: "uppercase",
    marginBottom: 10,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  summaryLabel: { fontSize: 13, color: "#94A3B8" },
  summaryValue: { fontSize: 14, fontWeight: "700", color: "#F8FAFC" },
  submitBtn: {
    marginTop: 14,
    backgroundColor: "#22C55E",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  submitText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  cancelBtn: {
    marginTop: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  cancelText: { color: "#94A3B8", fontSize: 13 },
});
