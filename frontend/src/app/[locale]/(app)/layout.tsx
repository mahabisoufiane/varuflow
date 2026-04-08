import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import AppShell from "@/components/app/AppShell";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
const IS_DEV = process.env.NODE_ENV === "development";

const ENFORCE_AUTH =
  process.env.SUPABASE_ENFORCE_AUTH === "true" ||
  (!IS_DEV && Boolean(SUPABASE_URL && SUPABASE_KEY)) ||
  (Boolean(SUPABASE_URL) &&
    !SUPABASE_URL.includes("localhost") &&
    !SUPABASE_URL.includes("127.0.0.1"));

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (ENFORCE_AUTH) {
    try {
      const supabase = await createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) redirect("/auth/login");
    } catch {
      if (!IS_DEV) redirect("/auth/login");
    }
  }

  // AiChat, CommandPalette, PwaInstallBanner are rendered inside AppShell
  // (a client component) gated by isClient, so they never run during SSR.
  return <AppShell>{children}</AppShell>;
}
