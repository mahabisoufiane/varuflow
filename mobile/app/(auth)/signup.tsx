// File: mobile/app/(auth)/signup.tsx
// Purpose: Signup screen — dark glass card, Supabase email/password registration
// Used by: login screen link, root layout

import React, { useState } from "react";
import {
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
  name?:     string;
  email?:    string;
  password?: string;
}

function getStrength(pw: string): { label: string; color: string; pct: number } {
  let score = 0;
  if (pw.length >= 8)          score++;
  if (/[A-Z]/.test(pw))        score++;
  if (/[0-9]/.test(pw))        score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const map = [
    { label: "",        color: "transparent", pct: 0   },
    { label: "Weak",    color: "#EF4444",      pct: 25  },
    { label: "Fair",    color: "#F59E0B",      pct: 50  },
    { label: "Good",    color: "#3B82F6",      pct: 75  },
    { label: "Strong",  color: "#22C55E",      pct: 100 },
  ];
  return map[score];
}

export default function SignupScreen() {
  const [name,     setName]     = useState("");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [fields,   setFields]   = useState<FieldErrors>({});
  const [done,     setDone]     = useState(false);

  const strength = getStrength(password);

  function validate(): boolean {
    const errs: FieldErrors = {};
    if (!name.trim())       errs.name     = "Name is required";
    if (!email.trim())      errs.email    = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
                            errs.email    = "Enter a valid email";
    if (!password)          errs.password = "Password is required";
    else if (password.length < 8)
                            errs.password = "Password must be at least 8 characters";
    setFields(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSignup() {
    if (!validate()) return;
    setLoading(true);
    setError(null);

    const { error: authErr } = await supabase.auth.signUp({
      email:    email.trim().toLowerCase(),
      password,
      options:  { data: { full_name: name.trim() } },
    });

    setLoading(false);

    if (authErr) {
      if (authErr.message.includes("already registered") ||
          authErr.message.includes("already exists")) {
        setError("An account with this email already exists. Try signing in.");
      } else if (authErr.message.includes("Password should")) {
        setError("Password must be at least 8 characters with letters and numbers.");
      } else {
        setError("Sign up failed. Please check your connection and try again.");
      }
      return;
    }

    setDone(true);
  }

  if (done) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.doneContainer}>
          <View style={styles.doneIcon}>
            <LinearGradient colors={["#22C55E", "#16A34A"]} style={styles.doneIconGrad}>
              <Text style={{ fontSize: 36 }}>✉️</Text>
            </LinearGradient>
          </View>
          <Text style={styles.doneHeading}>Check your email</Text>
          <Text style={styles.doneSub}>
            We've sent a confirmation link to{"\n"}
            <Text style={styles.doneEmail}>{email}</Text>
            {"\n\n"}Click the link to verify your account, then come back to sign in.
          </Text>
          <Button
            label="Back to Sign In"
            onPress={() => router.replace("/(auth)/login")}
          />
        </View>
      </SafeAreaView>
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
            <Text style={styles.heading}>Create account</Text>
            <Text style={styles.sub}>Join Varuflow today</Text>

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
                label="Full name"
                placeholder="Anna Svensson"
                value={name}
                onChangeText={(v) => { setName(v); setFields((f) => ({ ...f, name: undefined })); }}
                autoComplete="name"
                error={fields.name}
              />
              <Input
                label="Work email"
                placeholder="you@company.com"
                value={email}
                onChangeText={(v) => { setEmail(v); setFields((f) => ({ ...f, email: undefined })); }}
                keyboardType="email-address"
                autoComplete="email"
                error={fields.email}
              />
              <Input
                label="Password"
                placeholder="Min. 8 characters"
                value={password}
                onChangeText={(v) => { setPassword(v); setFields((f) => ({ ...f, password: undefined })); }}
                isPassword
                autoComplete="new-password"
                error={fields.password}
              />

              {/* Password strength bar */}
              {password.length > 0 && (
                <View style={styles.strengthWrap}>
                  <View style={styles.strengthBar}>
                    <View
                      style={[
                        styles.strengthFill,
                        { width: `${strength.pct}%` as unknown as number, backgroundColor: strength.color },
                      ]}
                    />
                  </View>
                  {strength.label ? (
                    <Text style={[styles.strengthLabel, { color: strength.color }]}>{strength.label}</Text>
                  ) : null}
                </View>
              )}
            </View>

            <Button label="Create account" onPress={handleSignup} loading={loading} />

            <Text style={styles.terms}>
              By signing up you agree to our{" "}
              <Text style={styles.termsLink}>Terms of Service</Text>
              {" "}and{" "}
              <Text style={styles.termsLink}>Privacy Policy</Text>.
            </Text>
          </View>

          {/* Sign in link */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>Already have an account? </Text>
            <Pressable onPress={() => router.replace("/(auth)/login")} hitSlop={8}>
              <Text style={styles.footerLink}>Sign in</Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: "#0F172A" },
  kav:           { flex: 1 },
  scroll:        { flexGrow: 1, paddingHorizontal: 24, paddingTop: 16, paddingBottom: 40 },
  topRow:        { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 32 },
  logoWrap:      { flexDirection: "row", alignItems: "center", gap: 10 },
  logoGrad:      { width: 36, height: 36, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  logoEmoji:     { fontSize: 18 },
  brand:         { fontSize: 20, fontWeight: "700", color: "#F8FAFC", letterSpacing: -0.3 },
  card:          {
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius:    20,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.08)",
    padding:         24,
  },
  heading:       { fontSize: 24, fontWeight: "700", color: "#F8FAFC", marginBottom: 4 },
  sub:           { fontSize: 14, color: "#64748B", marginBottom: 20 },
  errorBanner:   {
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
  errorBannerIcon:  { fontSize: 14, color: "#EF4444", marginTop: 1 },
  errorBannerText:  { flex: 1, fontSize: 13, color: "#FCA5A5", lineHeight: 19 },
  form:          { gap: 12, marginBottom: 16 },
  strengthWrap:  { flexDirection: "row", alignItems: "center", gap: 10, marginTop: -4 },
  strengthBar:   { flex: 1, height: 3, backgroundColor: "rgba(255,255,255,0.08)", borderRadius: 2, overflow: "hidden" },
  strengthFill:  { height: "100%", borderRadius: 2 },
  strengthLabel: { fontSize: 11, fontWeight: "500", minWidth: 40 },
  terms:         { fontSize: 11, color: "#475569", textAlign: "center", lineHeight: 16, marginTop: 12 },
  termsLink:     { color: "#6366F1" },
  footer:        { flexDirection: "row", justifyContent: "center", marginTop: 24 },
  footerText:    { fontSize: 14, color: "#64748B" },
  footerLink:    { fontSize: 14, color: "#6366F1", fontWeight: "600" },
  // Done state
  doneContainer: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 32 },
  doneIcon:      { marginBottom: 28 },
  doneIconGrad:  { width: 80, height: 80, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  doneHeading:   { fontSize: 26, fontWeight: "700", color: "#F8FAFC", marginBottom: 14, textAlign: "center" },
  doneSub:       { fontSize: 14, lineHeight: 22, color: "#94A3B8", textAlign: "center", marginBottom: 28 },
  doneEmail:     { color: "#818CF8", fontWeight: "600" },
});
