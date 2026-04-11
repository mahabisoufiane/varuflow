// File: mobile/app/_layout.tsx
// Purpose: Root layout — auth guard + enterprise plan check + push notification registration
// Flow: load session → if no session → /(auth)/login
//       if session → check plan → if not enterprise → show EnterpriseGate
//       else → /(app) tabs

import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Slot, router } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { supabase, getUserPlan }                  from "@/lib/supabase";
import { registerForPushNotifications }           from "@/lib/notifications";
import { EnterpriseGate }                         from "@/components/app/EnterpriseGate";
import type { Session }                           from "@supabase/supabase-js";

type AppState = "loading" | "unauthenticated" | "not_enterprise" | "ready";

export default function RootLayout() {
  const [appState, setAppState] = useState<AppState>("loading");
  const [session,  setSession]  = useState<Session | null>(null);

  useEffect(() => {
    // Initial session check
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      handleSession(s);
    });

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      handleSession(s);
    });

    return () => subscription.unsubscribe();
  }, []);

  async function handleSession(s: Session | null) {
    if (!s) {
      setSession(null);
      setAppState("unauthenticated");
      router.replace("/(auth)/login");
      return;
    }

    setSession(s);

    // Check enterprise plan
    const plan = await getUserPlan(s.user.id);
    if (plan !== "enterprise") {
      setAppState("not_enterprise");
      return;
    }

    // Register push notifications (non-blocking)
    registerForPushNotifications(s.user.id).catch(() => {});

    setAppState("ready");
    router.replace("/(app)/dashboard");
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    // onAuthStateChange fires → handleSession(null) → navigates to login
  }

  if (appState === "loading") {
    return (
      <View style={styles.splash}>
        <StatusBar style="light" />
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  if (appState === "not_enterprise") {
    return (
      <>
        <StatusBar style="light" />
        <EnterpriseGate onSignOut={handleSignOut} />
      </>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Slot />
    </>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex:            1,
    backgroundColor: "#0F172A",
    alignItems:      "center",
    justifyContent:  "center",
  },
});
