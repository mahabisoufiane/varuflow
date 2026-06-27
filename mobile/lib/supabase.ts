// File: mobile/lib/supabase.ts
// Purpose: Supabase client using AsyncStorage for React Native session persistence
// Used by: login, signup, root layout, all screens

import "react-native-url-polyfill/auto";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl  = process.env.EXPO_PUBLIC_SUPABASE_URL!;
const supabaseAnon = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnon, {
  auth: {
    storage:            AsyncStorage,
    autoRefreshToken:   true,
    persistSession:     true,
    detectSessionInUrl: false,
  },
});

// ── Plan helpers ─────────────────────────────────────────────────────────────

export type Plan = "starter" | "professional" | "enterprise";

export async function getUserPlan(userId: string): Promise<Plan> {
  const { data, error } = await supabase
    .from("profiles")
    .select("plan")
    .eq("id", userId)
    .single();
  // Propagate DB/network errors so the caller can distinguish "plan is
  // starter" from "couldn't reach the database". Silently returning
  // "starter" on error would lock enterprise users out of the app on any
  // transient network failure.
  if (error) throw error;
  return (data?.plan as Plan) ?? "starter";
}

export function isEnterprise(plan: Plan): boolean {
  return plan === "enterprise";
}

// ── Profile helpers ──────────────────────────────────────────────────────────

export interface UserProfile {
  id:         string;
  email:      string;
  full_name:  string | null;
  org_name:   string | null;
  plan:       Plan;
  push_token: string | null;
}

export async function getProfile(userId: string): Promise<UserProfile | null> {
  const { data, error } = await supabase
    .from("profiles")
    .select("id, email, full_name, org_name, plan, push_token")
    .eq("id", userId)
    .single();
  if (error) throw error;
  return data as UserProfile | null;
}

export async function updatePushToken(userId: string, token: string): Promise<void> {
  await supabase
    .from("profiles")
    .update({ push_token: token })
    .eq("id", userId);
}
