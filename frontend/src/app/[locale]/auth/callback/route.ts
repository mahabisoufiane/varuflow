import { createClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";

function safeNext(raw: string | null): string {
  if (!raw) return "/dashboard";
  // Only allow relative paths starting with /  — block open redirect to external URLs
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";
  // Block protocol-relative and encoded schemes (e.g. /%2F, /\, javascript:)
  const decoded = decodeURIComponent(raw);
  if (/^\/[/\\]/.test(decoded) || /javascript:/i.test(decoded)) return "/dashboard";
  return raw;
}

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeNext(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // Auth error — redirect to login with an error flag
  return NextResponse.redirect(`${origin}/auth/login?error=auth_callback_failed`);
}
