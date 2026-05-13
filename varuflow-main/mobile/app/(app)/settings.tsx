// File: mobile/app/(app)/settings.tsx
// Purpose: User and org settings — profile, notifications, plan badge, sign out
// Used by: bottom tab navigator

import React, { useEffect, useState } from "react";
import {
  Alert,
  Linking,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { supabase, getProfile } from "@/lib/supabase";
import { Card }                 from "@/components/ui/Card";
import { useDeviceLayout }      from "@/lib/useDeviceLayout";
import TabletTopBar             from "@/components/TabletTopBar";
import { listStockCountDrafts } from "@/lib/stock-count";
import { processPendingStockCounts } from "@/lib/stock-count-sync";
import { tStockCount }          from "@/lib/stock-count-i18n";

interface Profile {
  full_name:   string;
  email:       string;
  org_name:    string;
  plan:        string;
  avatar_url?: string;
}

interface NotifPrefs {
  lowStock:    boolean;
  newInvoice:  boolean;
  fortnoxSync: boolean;
}

export default function SettingsScreen() {
  const [profile,  setProfile]  = useState<Profile | null>(null);
  const [prefs,    setPrefs]    = useState<NotifPrefs>({ lowStock: true, newInvoice: true, fortnoxSync: false });
  const [loading,  setLoading]  = useState(true);
  const [draftStats, setDraftStats] = useState({ total: 0, pending: 0, synced: 0, failed: 0 });
  const { isTablet } = useDeviceLayout();

  useEffect(() => {
    (async () => {
      const drafts = await listStockCountDrafts();
      setDraftStats({
        total: drafts.length,
        pending: drafts.filter((d) => d.status === "submitted").length,
        synced: drafts.filter((d) => d.status === "synced").length,
        failed: drafts.filter((d) => d.status === "failed").length,
      });
    })();
  }, []);

  async function handleRetryPendingCounts() {
    await processPendingStockCounts();
    const drafts = await listStockCountDrafts();
    setDraftStats({
      total: drafts.length,
      pending: drafts.filter((d) => d.status === "submitted").length,
      synced: drafts.filter((d) => d.status === "synced").length,
      failed: drafts.filter((d) => d.status === "failed").length,
    });
    Alert.alert("Varuflow", tStockCount(null, "sync_status"));
  }

  useEffect(() => {
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      try {
        const raw = await getProfile(user.id);
        setProfile({
          full_name: user.user_metadata?.full_name ?? "User",
          email:     user.email ?? "",
          org_name:  raw?.org_name ?? "My Organisation",
          plan:      raw?.plan ?? "enterprise",
        });
      } catch {
        // Network/DB error — show whatever we have from the auth token
        setProfile({
          full_name: user.user_metadata?.full_name ?? "User",
          email:     user.email ?? "",
          org_name:  "My Organisation",
          plan:      "enterprise",
        });
      }
      setLoading(false);
    })();
  }, []);

  async function handleSignOut() {
    Alert.alert(
      "Sign out",
      "Are you sure you want to sign out?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text:    "Sign out",
          style:   "destructive",
          onPress: () => supabase.auth.signOut(),
        },
      ],
    );
  }

  function handleOpenBilling() {
    Linking.openURL("https://varuflow.vercel.app/en/settings?tab=billing");
  }

  function handleOpenDocs() {
    Linking.openURL("https://varuflow.vercel.app/en/docs");
  }

  if (loading || !profile) {
    return <SafeAreaView style={styles.safe} />;
  }

  const initials = profile.full_name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <SafeAreaView style={styles.safe}>
      {isTablet && <TabletTopBar title="Settings" testID="settings-tablet-topbar" />}
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        {!isTablet && <Text style={styles.pageTitle}>Settings</Text>}

        {/* Profile card */}
        <View style={styles.profileCard}>
          <LinearGradient colors={["#6366F1", "#4F46E5"]} style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </LinearGradient>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{profile.full_name}</Text>
            <Text style={styles.profileEmail}>{profile.email}</Text>
            <View style={styles.orgRow}>
              <Text style={styles.orgText}>{profile.org_name}</Text>
              <View style={styles.planBadge}>
                <Text style={styles.planText}>{profile.plan.toUpperCase()}</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Notifications + Account — tablet stacks them in a 2-column
            layout, phone keeps them in a vertical flow. */}
        <View
          testID={isTablet ? "settings-two-pane" : "settings-stack"}
          style={isTablet ? styles.twoPane : undefined}
        >
          <Card title="Notifications" style={[styles.section, isTablet && styles.paneCell]}>
            <NotifRow
              label="Low stock alerts"
              subtitle="Notify when items hit reorder level"
              value={prefs.lowStock}
              onChange={(v) => setPrefs((p) => ({ ...p, lowStock: v }))}
            />
            <NotifRow
              label="New invoices"
              subtitle="Notify when a new invoice is created"
              value={prefs.newInvoice}
              onChange={(v) => setPrefs((p) => ({ ...p, newInvoice: v }))}
            />
            <NotifRow
              label="Fortnox sync"
              subtitle="Notify after each sync completes"
              value={prefs.fortnoxSync}
              onChange={(v) => setPrefs((p) => ({ ...p, fortnoxSync: v }))}
              last
            />
          </Card>

          {/* Links */}
          <Card title="Account" style={[styles.section, isTablet && styles.paneCell]}>
            <Pressable
              testID="stock-count-drafts-row"
              style={notifStyles.row}
              onPress={handleRetryPendingCounts}
            >
              <Text style={notifStyles.emoji}>📋</Text>
              <View style={{ flex: 1 }}>
                <Text style={notifStyles.label}>Stock count drafts</Text>
                <Text style={notifStyles.sub}>
                  {draftStats.total} total · {draftStats.pending} pending · {draftStats.failed} failed
                </Text>
              </View>
              <Text style={notifStyles.chevron}>↻</Text>
            </Pressable>
            <View style={notifStyles.border} />
            <LinkRow label="Manage billing"      emoji="💳" onPress={handleOpenBilling} />
            <LinkRow label="Documentation"        emoji="📖" onPress={handleOpenDocs} />
            <LinkRow
              label="Open in browser"
              emoji="🌐"
              onPress={() => Linking.openURL("https://varuflow.vercel.app")}
              last
            />
          </Card>
        </View>

        {/* Sign out */}
        <Pressable style={styles.signOutBtn} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>

        {/* Version */}
        <Text style={styles.version}>Varuflow Mobile · v1.0.0</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function NotifRow({
  label, subtitle, value, onChange, last,
}: {
  label: string; subtitle?: string; value: boolean;
  onChange: (v: boolean) => void; last?: boolean;
}) {
  return (
    <View style={[notifStyles.row, !last && notifStyles.border]}>
      <View style={notifStyles.info}>
        <Text style={notifStyles.label}>{label}</Text>
        {subtitle && <Text style={notifStyles.sub}>{subtitle}</Text>}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: "#1E293B", true: "#4F46E5" }}
        thumbColor="#F8FAFC"
      />
    </View>
  );
}

function LinkRow({
  label, emoji, onPress, last,
}: {
  label: string; emoji: string; onPress: () => void; last?: boolean;
}) {
  return (
    <Pressable style={[notifStyles.row, !last && notifStyles.border]} onPress={onPress}>
      <Text style={notifStyles.emoji}>{emoji}</Text>
      <Text style={[notifStyles.label, { flex: 1 }]}>{label}</Text>
      <Text style={notifStyles.chevron}>›</Text>
    </Pressable>
  );
}

const notifStyles = StyleSheet.create({
  row:     { flexDirection: "row", alignItems: "center", paddingVertical: 12 },
  border:  { borderBottomWidth: 1, borderBottomColor: "rgba(255,255,255,0.05)" },
  info:    { flex: 1 },
  label:   { fontSize: 14, color: "#F1F5F9", fontWeight: "500" },
  sub:     { fontSize: 11, color: "#64748B", marginTop: 2 },
  emoji:   { fontSize: 18, marginRight: 12 },
  chevron: { fontSize: 20, color: "#475569", marginLeft: 8 },
});

const styles = StyleSheet.create({
  safe:         { flex: 1, backgroundColor: "#0F172A" },
  scroll:       { padding: 20, paddingBottom: 60 },
  pageTitle:    { fontSize: 22, fontWeight: "700", color: "#F8FAFC", marginBottom: 20 },
  profileCard:  {
    flexDirection:   "row",
    alignItems:      "center",
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius:    16,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.08)",
    padding:         16,
    gap:             14,
    marginBottom:    16,
  },
  avatar:       { width: 52, height: 52, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  avatarText:   { fontSize: 18, fontWeight: "700", color: "#fff" },
  profileInfo:  { flex: 1 },
  profileName:  { fontSize: 16, fontWeight: "700", color: "#F8FAFC" },
  profileEmail: { fontSize: 13, color: "#64748B", marginTop: 2 },
  orgRow:       { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 },
  orgText:      { fontSize: 12, color: "#94A3B8" },
  planBadge:    {
    backgroundColor: "rgba(99,102,241,0.15)",
    borderRadius:    5,
    paddingHorizontal: 7,
    paddingVertical:   2,
    borderWidth:     1,
    borderColor:     "rgba(99,102,241,0.35)",
  },
  planText:     { fontSize: 10, fontWeight: "700", color: "#818CF8", letterSpacing: 0.5 },
  section:      { marginBottom: 12 },
  signOutBtn:   {
    backgroundColor: "rgba(239,68,68,0.10)",
    borderRadius:    14,
    padding:         14,
    alignItems:      "center",
    borderWidth:     1,
    borderColor:     "rgba(239,68,68,0.25)",
    marginTop:       8,
    marginBottom:    16,
  },
  signOutText:  { fontSize: 15, fontWeight: "600", color: "#EF4444" },
  version:      { fontSize: 11, color: "#334155", textAlign: "center" },
  twoPane:      { flexDirection: "row", gap: 16 },
  paneCell:     { flex: 1 },
});
