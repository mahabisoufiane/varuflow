// File: src/app/[locale]/(app)/layout.tsx
// Purpose: Auth gate for all protected app routes — redirects to login if no session
// Used by: Every page under /[locale]/(app)/

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import ConsoleShell from "@/components/console/ConsoleShell";

// Auth is enforced whenever Supabase is configured with a real hosted project.
// In local dev without env vars the gate is skipped so the UI is explorable.
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const IS_DEV = process.env.NODE_ENV === "development";

const ENFORCE_AUTH =
  Boolean(SUPABASE_URL) &&
  !SUPABASE_URL.includes("placeholder.supabase.co") &&
  !SUPABASE_URL.includes("localhost") &&
  !SUPABASE_URL.includes("127.0.0.1");

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  // locale is available because this layout lives under /[locale]/
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (ENFORCE_AUTH) {
    try {
      const supabase = await createClient();
      const { data: { user } } = await supabase.auth.getUser();
      // Redirect preserves locale so the login page can use the right language
      if (!user) redirect(`/${locale}/auth/login`);
    } catch {
      // If Supabase is unreachable in production, fail closed — send to login
      if (!IS_DEV) redirect(`/${locale}/auth/login`);
    }
  }

  // The four-region operator console. Region 3 renders {children} (the real
  // route page), so all routing, i18n and permission guards are preserved.
  // Overlays (CommandPalette, AiChat, PwaInstallBanner, …) are mounted inside
  // ConsoleShell, gated to the client so they never run during SSR.
  return <ConsoleShell>{children}</ConsoleShell>;
}
