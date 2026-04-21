// File: mobile/app/_layout.tsx
// Purpose: Root layout — auth guard + enterprise plan check + push notification registration

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Slot, router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";

import { supabase, getUserPlan }        from "@/lib/supabase";
import { registerForPushNotifications } from "@/lib/notifications";
import { EnterpriseGate }               from "@/components/app/EnterpriseGate";

type AppState = "loading" | "unauthenticated" | "not_enterprise" | "ready";

export default function RootLayout() {
  const [appState, setAppState] = useState<AppState>("loading");
  // Keep a ref so handleAuthEvent never has a stale closure
  const appStateRef = useRef<AppState>("loading");

  function setState(s: AppState) {
    appStateRef.current = s;
    setAppState(s);
  }

  const handleAuthEvent = useCallback(
    async (event: AuthChangeEvent, session: Session | null) => {
      // Event semantics:
      //   TOKEN_REFRESHED / SIGNED_IN / INITIAL_SESSION → authenticated
      //   SIGNED_OUT                                    → user signed out
      //   TOKEN_REFRESH_FAILED                          → refresh failed, force re-auth
      //
      // TOKEN_REFRESH_FAILED is treated as a hard auth failure: the refresh
      // token is rejected by Supabase (revoked, expired, or tampered with).
      // We sign the user out explicitly and redirect to login. A transient
      // network error does NOT emit this event — Supabase retries silently —
      // so it's safe to treat every TOKEN_REFRESH_FAILED as a real failure.
      if ((event as string) === "TOKEN_REFRESH_FAILED") {
        await supabase.auth.signOut().catch(() => {});
        setState("unauthenticated");
        router.replace("/(auth)/login");
        return;
      }

      if (!session) {
        setState("unauthenticated");
        router.replace("/(auth)/login");
        return;
      }

      // Already ready — skip the plan re-check on every token refresh
      if (
        event === "TOKEN_REFRESHED" &&
        appStateRef.current === "ready"
      ) {
        return;
      }

      // New sign-in or initial session load → check plan
      const plan = await getUserPlan(session.user.id);
      if (plan !== "enterprise") {
        setState("not_enterprise");
        return;
      }

      // Register push (non-blocking, ignore errors)
      registerForPushNotifications(session.user.id).catch(() => {});

      setState("ready");

      // Only navigate if we aren't already in the app
      if (appStateRef.current !== "ready") {
        router.replace("/(app)/dashboard");
      } else {
        router.replace("/(app)/dashboard");
      }
    },
    [],
  );

  useEffect(() => {
    // onAuthStateChange fires immediately with INITIAL_SESSION
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        handleAuthEvent(event, session);
      },
    );

    return () => subscription.unsubscribe();
  }, [handleAuthEvent]);

  async function handleSignOut() {
    await supabase.auth.signOut();
    // onAuthStateChange fires SIGNED_OUT → handleAuthEvent → login
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

  if (appState === "unauthenticated") {
    // router.replace already called; render nothing while navigating
    return (
      <View style={styles.splash}>
        <StatusBar style="light" />
      </View>
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
