import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_CONFIGURED =
  Boolean(SUPABASE_URL) &&
  !SUPABASE_URL.includes("placeholder.supabase.co") &&
  !SUPABASE_URL.includes("localhost") &&
  !SUPABASE_URL.includes("127.0.0.1");

export default async function LocaleRootPage() {
  if (SUPABASE_CONFIGURED) {
    try {
      const supabase = await createClient();
      const { data: { user } } = await supabase.auth.getUser();
      // Logged in → go straight to app; not logged in → go to login
      redirect(user ? "/dashboard" : "/auth/login");
    } catch {
      redirect("/auth/login");
    }
  }

  // Local dev without Supabase — show login page so the
  // "Enter as Dev Owner" button is visible instead of dumping
  // straight into the dashboard.
  redirect("/auth/login");
}
