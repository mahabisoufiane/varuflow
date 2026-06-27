// File: mobile/app/(auth)/forgot-password.tsx
// Purpose: Forgot password screen — sends Supabase password-reset email

import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { router } from "expo-router";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/Button";
import { Input }  from "@/components/ui/Input";

export default function ForgotPasswordScreen() {
  const [email, setEmail]     = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent]       = useState(false);
  const [error, setError]     = useState<string | undefined>();

  async function handleReset() {
    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    setLoading(true);
    setError(undefined);
    const { error: err } = await supabase.auth.resetPasswordForEmail(email.trim());
    setLoading(false);
    if (err) {
      setError(err.message);
    } else {
      setSent(true);
    }
  }

  return (
    <LinearGradient colors={["#0F172A", "#1E293B"]} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.kav}
        >
          <View style={styles.card}>
            <Text style={styles.title}>Reset password</Text>

            {sent ? (
              <>
                <Text style={styles.body}>
                  Check your inbox — we sent a password-reset link to {email}.
                </Text>
                <Button label="Back to sign in" onPress={() => router.replace("/(auth)/login")} />
              </>
            ) : (
              <>
                <Text style={styles.body}>
                  Enter your account email and we'll send you a reset link.
                </Text>
                <Input
                  label="Email"
                  placeholder="you@company.com"
                  value={email}
                  onChangeText={(v) => { setEmail(v); setError(undefined); }}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoComplete="email"
                  error={error}
                />
                <Button label="Send reset link" onPress={handleReset} loading={loading} />
                <Text
                  style={styles.back}
                  onPress={() => router.back()}
                >
                  Back to sign in
                </Text>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe:     { flex: 1 },
  kav:      { flex: 1, justifyContent: "center", paddingHorizontal: 24 },
  card: {
    backgroundColor: "rgba(255,255,255,0.06)",
    borderRadius:    20,
    padding:         28,
    gap:             16,
  },
  title: {
    fontSize:   24,
    fontWeight: "700",
    color:      "#F8FAFC",
  },
  body: {
    fontSize:   14,
    color:      "#94A3B8",
    lineHeight: 20,
  },
  back: {
    fontSize:  13,
    color:     "#6366F1",
    textAlign: "center",
    marginTop: 4,
  },
});
