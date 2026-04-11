// File: mobile/components/app/EnterpriseGate.tsx
// Purpose: Full-screen gate shown when org plan is not "enterprise"
// Used by: root layout on startup after auth check

import React from "react";
import {
  Linking,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

interface EnterpriseGateProps {
  onSignOut: () => void;
}

export function EnterpriseGate({ onSignOut }: EnterpriseGateProps) {
  const handleUpgrade = () => {
    Linking.openURL("https://varuflow.vercel.app/en/settings?tab=billing");
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        {/* Icon */}
        <View style={styles.iconWrap}>
          <LinearGradient
            colors={["#6366F1", "#4F46E5"]}
            style={styles.iconGrad}
          >
            <Text style={styles.iconEmoji}>🏢</Text>
          </LinearGradient>
        </View>

        {/* Copy */}
        <Text style={styles.heading}>Enterprise Plan Required</Text>
        <Text style={styles.body}>
          The Varuflow mobile app is available exclusively on the{" "}
          <Text style={styles.highlight}>Enterprise plan</Text>.{"\n\n"}
          Upgrade your organisation to unlock real-time inventory, mobile
          notifications, and offline access.
        </Text>

        {/* Feature list */}
        <View style={styles.features}>
          {FEATURES.map((f) => (
            <View key={f.label} style={styles.featureRow}>
              <View style={styles.featureDot} />
              <Text style={styles.featureText}>{f.label}</Text>
            </View>
          ))}
        </View>

        {/* Actions */}
        <Pressable onPress={handleUpgrade} style={styles.upgradeBtn}>
          <LinearGradient
            colors={["#6366F1", "#4F46E5"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.upgradeBtnGrad}
          >
            <Text style={styles.upgradeBtnText}>Upgrade to Enterprise</Text>
          </LinearGradient>
        </Pressable>

        <Pressable onPress={onSignOut} style={styles.signOutBtn} hitSlop={8}>
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const FEATURES = [
  { label: "Real-time inventory sync" },
  { label: "Push notifications for low stock & invoices" },
  { label: "Mobile-first order management" },
  { label: "Offline access with auto-sync" },
  { label: "Fortnox integration on mobile" },
];

const styles = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: "#0F172A" },
  container:     {
    flex:            1,
    alignItems:      "center",
    justifyContent:  "center",
    paddingHorizontal: 32,
  },
  iconWrap:      { marginBottom: 28 },
  iconGrad:      {
    width:           80,
    height:          80,
    borderRadius:    24,
    alignItems:      "center",
    justifyContent:  "center",
  },
  iconEmoji:     { fontSize: 36 },
  heading:       {
    fontSize:    26,
    fontWeight:  "700",
    color:       "#F8FAFC",
    textAlign:   "center",
    marginBottom: 14,
  },
  body:          {
    fontSize:   14,
    lineHeight: 22,
    color:      "#94A3B8",
    textAlign:  "center",
    marginBottom: 24,
  },
  highlight:     { color: "#818CF8", fontWeight: "600" },
  features:      {
    alignSelf:    "stretch",
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius:    12,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.07)",
    padding:         16,
    marginBottom:    28,
    gap:             10,
  },
  featureRow:    { flexDirection: "row", alignItems: "center", gap: 10 },
  featureDot:    {
    width:           6,
    height:          6,
    borderRadius:    3,
    backgroundColor: "#6366F1",
  },
  featureText:   { fontSize: 13, color: "#CBD5E1" },
  upgradeBtn:    { alignSelf: "stretch", borderRadius: 14, overflow: "hidden", marginBottom: 14 },
  upgradeBtnGrad:{ paddingVertical: 14, alignItems: "center" },
  upgradeBtnText:{ fontSize: 15, fontWeight: "700", color: "#fff", letterSpacing: 0.2 },
  signOutBtn:    { paddingVertical: 8 },
  signOutText:   { fontSize: 13, color: "#64748B" },
});
