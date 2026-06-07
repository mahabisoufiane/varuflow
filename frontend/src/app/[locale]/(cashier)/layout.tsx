import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const IS_DEV = process.env.NODE_ENV === "development";

const ENFORCE_AUTH =
  Boolean(SUPABASE_URL) &&
  !SUPABASE_URL.includes("placeholder.supabase.co") &&
  !SUPABASE_URL.includes("localhost") &&
  !SUPABASE_URL.includes("127.0.0.1");

export default async function CashierLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (ENFORCE_AUTH) {
    try {
      const supabase = await createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) redirect(`/${locale}/auth/login`);
    } catch {
      if (!IS_DEV) redirect(`/${locale}/auth/login`);
    }
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-gray-900">
      {children}
    </div>
  );
}
