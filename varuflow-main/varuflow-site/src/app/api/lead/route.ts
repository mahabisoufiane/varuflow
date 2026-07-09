import { NextResponse } from "next/server";
import { leadSchema } from "@/lib/lead";

// Demo requests are forwarded into the Varuflow app's public waitlist
// endpoint so they land in the product database (visible to the founder)
// with zero external services. If the backend is unreachable the lead is
// still logged and the visitor still sees success.
const APP_API = process.env.APP_API_URL ?? "https://varuflow-production.up.railway.app";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  const parsed = leadSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: "validation", issues: parsed.error.issues },
      { status: 422 },
    );
  }

  const lead = parsed.data;
  console.log("[lead] demo request", { ...lead, receivedAt: new Date().toISOString() });

  try {
    const company_name = `${lead.company} — ${lead.name} (demo, ${lead.size})${
      lead.message ? `: ${lead.message}` : ""
    }`.slice(0, 255);
    const res = await fetch(`${APP_API}/api/waitlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: lead.email, company_name }),
    });
    if (!res.ok && res.status !== 409) {
      console.error("[lead] forward failed:", res.status);
    }
  } catch (e) {
    // TODO: replace with a dedicated leads/CRM endpoint + retry queue.
    console.error("[lead] forward unreachable:", e);
  }

  return NextResponse.json({ ok: true });
}
