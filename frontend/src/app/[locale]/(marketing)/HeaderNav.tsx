"use client";

import { useEffect, useState } from "react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";
import { createClient } from "@/lib/supabase/client";

export default function MarketingHeaderNav() {
  const pathname = usePathname();
  const router = useRouter();
  const locale = useLocale();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    if (!supabase) return;
    supabase.auth.getUser().then(({ data }) => {
      setIsLoggedIn(!!data.user);
    });
  }, []);

  function switchLocale(next: "sv" | "en") {
    router.replace(pathname, { locale: next });
  }

  return (
    <div className="flex items-center gap-4">
      {/* Locale switcher */}
      <div className="flex items-center gap-1 rounded-md border p-0.5" style={{ borderColor: "rgba(255,255,255,0.12)" }}>
        <button
          onClick={() => switchLocale("sv")}
          className="rounded px-2.5 py-1 text-xs font-medium transition-colors"
          style={{
            background: locale === "sv" ? "rgba(255,255,255,0.15)" : "transparent",
            color: locale === "sv" ? "#fff" : "rgba(255,255,255,0.45)",
          }}
        >
          SV
        </button>
        <button
          onClick={() => switchLocale("en")}
          className="rounded px-2.5 py-1 text-xs font-medium transition-colors"
          style={{
            background: locale === "en" ? "rgba(255,255,255,0.15)" : "transparent",
            color: locale === "en" ? "#fff" : "rgba(255,255,255,0.45)",
          }}
        >
          EN
        </button>
      </div>

      {/* Nav links */}
      <Link
        href="/pricing"
        className="text-sm font-medium transition-colors"
        style={{ color: "rgba(255,255,255,0.6)" }}
      >
        Pricing
      </Link>

      {/* Auth-aware CTA */}
      {isLoggedIn ? (
        <Link
          href="/dashboard"
          className="rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
          style={{ background: "rgba(255,255,255,0.12)", color: "#fff" }}
        >
          Go to app
        </Link>
      ) : (
        <Link
          href="/auth/signup"
          className="rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
          style={{ background: "linear-gradient(135deg,#6366f1,#7c3aed)", color: "#fff" }}
        >
          Get started
        </Link>
      )}
    </div>
  );
}
