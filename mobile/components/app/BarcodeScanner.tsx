// File: mobile/components/app/BarcodeScanner.tsx
// Purpose: Full-screen camera scanner with quick stock-movement actions.
// Used by:   inventory screen ("Skanna produkt" button).
//
// Flow:
//   1. Request camera permission (cached by the OS after the first grant).
//   2. Start CameraView in barcode-scan mode.
//   3. On first successful scan → GET /api/inventory/products?barcode=…
//      (single-shot; we disable further scans until the user closes the
//      result card so a twitchy finger can't spam duplicate scans).
//   4. Result card offers +1 IN / -1 OUT / View details.
//   5. Movements go to POST /api/inventory/movements with quantity=1
//      and haptic feedback on success.

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Modal,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import { apiClient, ApiError } from "@/lib/api-client";

// Keep this list to formats a handheld phone actually resolves well.
// Full 2D support (data-matrix etc.) is retail POS territory, not us.
const BARCODE_TYPES = [
  "ean13",
  "ean8",
  "upc_a",
  "upc_e",
  "code128",
  "code39",
  "qr",
];

type Product = {
  id: string;
  name: string;
  sku: string;
  barcode?: string | null;
  unit: string;
  is_active: boolean;
  stock_levels?: { warehouse_id: string; quantity: number }[];
};

type Warehouse = { id: string; name: string; is_active: boolean };

type ListResp = { items: Product[]; total: number };
type WarehouseListResp = { items: Warehouse[]; total: number } | Warehouse[];

type ToastFn = (message: string, kind?: "success" | "error") => void;

interface Props {
  visible: boolean;
  onClose: () => void;
  onViewDetails?: (product: Product) => void;
  toast: ToastFn;
}

export default function BarcodeScanner({ visible, onClose, onViewDetails, toast }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [product, setProduct] = useState<Product | null>(null);
  const [warehouse, setWarehouse] = useState<Warehouse | null>(null);
  const [looking, setLooking] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  // Lock out further scans while we handle the last one; cleared when
  // the user dismisses the result card.
  const scannedRef = useRef<string | null>(null);

  // Lazily fetch the first active warehouse so stock movements can be
  // recorded in one tap. Organisations with multiple warehouses get
  // the deterministic first-by-name — a detail screen can always move
  // stock between warehouses later.
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await apiClient.get<WarehouseListResp>(
          "/api/inventory/warehouses",
        );
        const list = Array.isArray(res) ? res : res.items;
        const active = list.find((w) => w.is_active) ?? list[0];
        if (!cancelled) setWarehouse(active ?? null);
      } catch {
        if (!cancelled) setWarehouse(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [visible]);

  const reset = useCallback(() => {
    scannedRef.current = null;
    setProduct(null);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [onClose, reset]);

  const onBarcodeScanned = useCallback(
    async ({ data }: { data: string }) => {
      if (!data || scannedRef.current) return;
      scannedRef.current = data;
      setLooking(true);
      try {
        const res = await apiClient.get<ListResp>(
          `/api/inventory/products?barcode=${encodeURIComponent(data)}`,
        );
        if (!res.items.length) {
          toast("Produkt hittades ej", "error");
          scannedRef.current = null;
          return;
        }
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        setProduct(res.items[0]);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          toast("Produkt hittades ej", "error");
        } else {
          toast(err instanceof Error ? err.message : "Skanningen misslyckades", "error");
        }
        // Allow retrying the same barcode once we showed the toast.
        scannedRef.current = null;
      } finally {
        setLooking(false);
      }
    },
    [toast],
  );

  async function quickMovement(type: "IN" | "OUT") {
    if (!product || !warehouse || busyAction) return;
    setBusyAction(true);
    try {
      await apiClient.post("/api/inventory/movements", {
        product_id: product.id,
        warehouse_id: warehouse.id,
        type,
        quantity: 1,
        reference: "scan",
        note: `Skannad via mobil (${type})`,
      });
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      toast(
        type === "IN" ? "+1 IN bokförd" : "-1 OUT bokförd",
        "success",
      );
      reset();
    } catch (err) {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      toast(err instanceof Error ? err.message : "Kunde inte bokföra", "error");
    } finally {
      setBusyAction(false);
    }
  }

  // ── Permission gate ──────────────────────────────────────────────
  if (!permission) {
    return null; // still loading the first time
  }
  if (!permission.granted) {
    return (
      <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
        <SafeAreaView style={styles.permissionWrap}>
          <Text style={styles.permissionTitle}>Kameraåtkomst krävs</Text>
          <Text style={styles.permissionBody}>
            Tillåt Varuflow att använda kameran för att skanna streckkoder.
          </Text>
          <Pressable
            style={styles.primaryBtn}
            onPress={async () => {
              const r = await requestPermission();
              // On iOS a previously-denied permission can only be
              // re-granted from Settings; fall back to deep-link.
              if (!r.granted && !r.canAskAgain) {
                Linking.openSettings();
              }
            }}
          >
            <Text style={styles.primaryBtnText}>Tillåt kamera</Text>
          </Pressable>
          <Pressable style={styles.secondaryBtn} onPress={handleClose}>
            <Text style={styles.secondaryBtnText}>Avbryt</Text>
          </Pressable>
        </SafeAreaView>
      </Modal>
    );
  }

  // Lag aggregate stock across warehouses — matches what the user
  // expects when they ask "how much do we have?"
  const onHand = (product?.stock_levels ?? []).reduce(
    (sum, sl) => sum + (sl.quantity ?? 0),
    0,
  );

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
      <View style={styles.cameraWrap}>
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: BARCODE_TYPES }}
          onBarcodeScanned={product ? undefined : onBarcodeScanned}
        />
        <SafeAreaView style={styles.overlay} pointerEvents="box-none">
          <View style={styles.overlayTop}>
            <Pressable style={styles.closeBtn} onPress={handleClose} hitSlop={12}>
              <Text style={styles.closeBtnText}>✕</Text>
            </Pressable>
            <Text style={styles.overlayTitle}>Skanna streckkod</Text>
            <View style={{ width: 36 }} />
          </View>

          {/* Reticle */}
          <View pointerEvents="none" style={styles.reticleWrap}>
            <View style={styles.reticle} />
            {looking && (
              <ActivityIndicator
                color="#F8FAFC"
                size="large"
                style={{ marginTop: 24 }}
              />
            )}
          </View>

          {/* Result card */}
          {product && (
            <View style={styles.resultCard}>
              <Text style={styles.productName} numberOfLines={2}>
                {product.name}
              </Text>
              <Text style={styles.productMeta}>
                SKU {product.sku} · {onHand} {product.unit}
                {warehouse ? `  ·  ${warehouse.name}` : ""}
              </Text>
              <View style={styles.actionRow}>
                <Pressable
                  style={[styles.actionBtn, styles.actionIn]}
                  disabled={busyAction || !warehouse}
                  onPress={() => quickMovement("IN")}
                >
                  <Text style={styles.actionText}>+1 IN</Text>
                </Pressable>
                <Pressable
                  style={[styles.actionBtn, styles.actionOut]}
                  disabled={busyAction || !warehouse}
                  onPress={() => quickMovement("OUT")}
                >
                  <Text style={styles.actionText}>-1 OUT</Text>
                </Pressable>
                {onViewDetails && (
                  <Pressable
                    style={[styles.actionBtn, styles.actionDetail]}
                    onPress={() => {
                      const p = product;
                      handleClose();
                      onViewDetails(p);
                    }}
                  >
                    <Text style={styles.actionText}>Detaljer</Text>
                  </Pressable>
                )}
              </View>
              <Pressable style={styles.rescanBtn} onPress={reset}>
                <Text style={styles.rescanText}>Skanna igen</Text>
              </Pressable>
              {!warehouse && (
                <Text style={styles.warn}>
                  Inget aktivt lager finns — rörelser kan inte bokföras.
                </Text>
              )}
            </View>
          )}
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  cameraWrap: { flex: 1, backgroundColor: "#000" },
  overlay: { flex: 1, justifyContent: "space-between" },
  overlayTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  closeBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center", justifyContent: "center",
  },
  closeBtnText: { color: "#F8FAFC", fontSize: 18, fontWeight: "700" },
  overlayTitle: { color: "#F8FAFC", fontSize: 15, fontWeight: "600" },
  reticleWrap: { alignItems: "center", justifyContent: "center" },
  reticle: {
    width: 260, height: 160,
    borderWidth: 2, borderColor: "rgba(129,140,248,0.9)",
    borderRadius: 12,
  },
  resultCard: {
    margin: 16, padding: 18, borderRadius: 16,
    backgroundColor: "rgba(15,23,42,0.95)",
    borderWidth: 1, borderColor: "rgba(255,255,255,0.1)",
  },
  productName: { color: "#F8FAFC", fontSize: 17, fontWeight: "700" },
  productMeta: { color: "#94A3B8", fontSize: 13, marginTop: 4 },
  actionRow: { flexDirection: "row", marginTop: 14, gap: 8 },
  actionBtn: {
    flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: "center",
  },
  actionIn:     { backgroundColor: "rgba(34,197,94,0.25)", borderWidth: 1, borderColor: "rgba(34,197,94,0.5)" },
  actionOut:    { backgroundColor: "rgba(239,68,68,0.25)", borderWidth: 1, borderColor: "rgba(239,68,68,0.5)" },
  actionDetail: { backgroundColor: "rgba(99,102,241,0.20)", borderWidth: 1, borderColor: "rgba(99,102,241,0.5)" },
  actionText: { color: "#F8FAFC", fontWeight: "700", fontSize: 13 },
  rescanBtn: { alignSelf: "center", marginTop: 12, padding: 6 },
  rescanText: { color: "#818CF8", fontSize: 13, fontWeight: "600" },
  warn: { color: "#F59E0B", fontSize: 12, marginTop: 10, textAlign: "center" },
  permissionWrap: {
    flex: 1, backgroundColor: "#0F172A",
    alignItems: "center", justifyContent: "center", padding: 24,
  },
  permissionTitle: { color: "#F8FAFC", fontSize: 18, fontWeight: "700", marginBottom: 10 },
  permissionBody: { color: "#94A3B8", fontSize: 14, textAlign: "center", marginBottom: 20 },
  primaryBtn: {
    paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10,
    backgroundColor: "#6366F1",
  },
  primaryBtnText: { color: "#F8FAFC", fontWeight: "700" },
  secondaryBtn: { marginTop: 10, padding: 10 },
  secondaryBtnText: { color: "#94A3B8", fontSize: 13 },
});
