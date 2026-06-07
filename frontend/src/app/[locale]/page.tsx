import { redirect } from "next/navigation";

/**
 * Root locale page — redirect to dashboard.
 * Auth gate in (app)/layout.tsx is skipped when NEXT_PUBLIC_SUPABASE_URL is empty
 * (local dev without Supabase), so this lands straight in the app.
 * In production the auth gate will redirect to login if there's no session.
 */
export default function LocaleRootPage() {
  redirect("/dashboard");
}
