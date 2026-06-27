// File: mobile/app/(auth)/login.tsx
// Purpose: Login screen — dark glass card, Supabase email/password auth
// Used by: root layout when no session

import React, { useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { router } from "expo-router";
import { supabase } from "@/lib/supabase";
import { Button }      from "@/components/ui/Button";
import { Input }       from "@/components/ui/Input";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

interface FieldErrors {
  email?:    string;
  password?: string;
}

export default function LoginScreen() {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [fields,   setFields]   = useState<FieldErrors>({});

  function validate(): boolean {
    const errs: FieldErrors = {};
    if (!email.trim())      errs.email    = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
                            errs.email    = "Enter a valid email";
    if (!password)          errs.password = "Password is required";
    setFields(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleLogin() {
    if (!validate()) return;
    setLoading(true);
    setError(null);

    const { error: authErr } = await supabase.auth.signInWithPassword({
      email:    email.trim().toLowerCase(),
      password,
    });

    setLoading(false);

    if (authErr) {
      if (authErr.message.includes("Invalid login credentials") ||
          authErr.message.includes("invalid_credentials")) {
        setError("Incorrect email or password. Please try again.");
      } else if (authErr.message.includes("Email not confirmed")) {
        setError("Please verify your email before signing in.");
      } else if (authErr.message.includes("Too many requests")) {
        setError("Too many attempts. Please wait a moment and try again.");
      } else {
        setError("Sign in failed. Please check your connection and try again.");
      }
      return;
    }

    // Navigation handled by root layout session listener
  }

  async function handleGoogleOAuth() {
    Alert.alert(
      "OAuth",
      "Google sign-in is available in the browser. Open varuflow.vercel.app to continue.",
      [{ text: "OK" }],
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.kav}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Header row */}
          <View style={styles.topRow}>
            <View style={styles.logoWrap}>
              <LinearGradient colors={["#6366F1", "#4F46E5"]} style={styles.logoGrad}>
                <Text style={styles.logoEmoji}>⚡</Text>
              </LinearGradient>
              <Text style={styles.brand}>Varuflow</Text>
            </View>
            <ThemeToggle />
          </View>

          {/* Glass card */}
          <View style={styles.card}>
            <Text style={styles.heading}>Welcome back</Text>
            <Text style={styles.sub}>Sign in to your account</Text>

            {/* Error banner */}
            {error && (
              <View style={styles.errorBanner}>
                <Text style={styles.errorBannerIcon}>⚠</Text>
                <Text style={styles.errorBannerText}>{error}</Text>
              </View>
            )}

            {/* Form */}
            <View style={styles.form}>
              <Input
                label="Email"
                placeholder="you@company.com"
                value={email}
                onChangeText={(v) => { setEmail(v); setFields((f) => ({ ...f, email: undefined })); }}
                keyboardType="email-address"
                autoComplete="email"
                error={fields.email}
              />
              <Input
                label="Password"
                placeholder="••••••••"
                value={password}
                onChangeText={(v) => { setPassword(v); setFields((f) => ({ ...f, password: undefined })); }}
                isPassword
                autoComplete="current-password"
                error={fields.password}
              />
            </View>

            {/* Forgot password */}
            <Pressable
              onPress={() => router.push("/(auth)/forgot-password")}
              style={styles.forgotWrap}
              hitSlop={8}
            >
              <Text style={styles.forgotText}>Forgot password?</Text>
            </Pressable>

            <Button label="Sign in" onPress={handleLogin} loading={loading} />

            {/* Divider */}
            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.dividerLine} />
            </View>

            {/* Google OAuth */}
            <Button
              label="Continue with Google"
              onPress={handleGoogleOAuth}
              variant="ghost"
              icon={<Text style={{ fontSize: 16 }}>G</Text>}
            />
          </View>

          {/* Sign up link */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>Don't have an account? </Text>
            <Pressable onPress={() => router.replace("/(auth)/signup")} hitSlop={8}>
              <Text style={styles.footerLink}>Sign up</Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:         { flex: 1, backgroundColor: "#0F172A" },
  kav:          { flex: 1 },
  scroll:       { flexGrow: 1, paddingHorizontal: 24, paddingTop: 16, paddingBottom: 40 },
  topRow:       { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 32 },
  logoWrap:     { flexDirection: "row", alignItems: "center", gap: 10 },
  logoGrad:     { width: 36, height: 36, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  logoEmoji:    { fontSize: 18 },
  brand:        { fontSize: 20, fontWeight: "700", color: "#F8FAFC", letterSpacing: -0.3 },
  card:         {
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius:    20,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.08)",
    padding:         24,
  },
  heading:      { fontSize: 24, fontWeight: "700", color: "#F8FAFC", marginBottom: 4 },
  sub:          { fontSize: 14, color: "#64748B", marginBottom: 20 },
  errorBanner:  {
    flexDirection:   "row",
    alignItems:      "flex-start",
    gap:             10,
    backgroundColor: "rgba(239,68,68,0.10)",
    borderWidth:     1,
    borderColor:     "rgba(239,68,68,0.35)",
    borderRadius:    10,
    padding:         12,
    marginBottom:    16,
  },
  errorBannerIcon: { fontSize: 14, color: "#EF4444", marginTop: 1 },
  errorBannerText: { flex: 1, fontSize: 13, color: "#FCA5A5", lineHeight: 19 },
  form:         { gap: 12, marginBottom: 8 },
  forgotWrap:   { alignItems: "flex-end", marginBottom: 16, marginTop: 4 },
  forgotText:   { fontSize: 13, color: "#6366F1" },
  divider:      { flexDirection: "row", alignItems: "center", gap: 10, marginVertical: 16 },
  dividerLine:  { flex: 1, height: 1, backgroundColor: "rgba(255,255,255,0.08)" },
  dividerText:  { fontSize: 12, color: "#475569" },
  footer:       { flexDirection: "row", justifyContent: "center", marginTop: 24 },
  footerText:   { fontSize: 14, color: "#64748B" },
  footerLink:   { fontSize: 14, color: "#6366F1", fontWeight: "600" },
});
