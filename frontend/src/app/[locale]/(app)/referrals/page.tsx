"use client";
// frontend/src/app/[locale]/(app)/referrals/page.tsx
// Operator-to-operator referral program — earn rewards by referring other businesses.

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { toast } from "sonner";
import {
  Link2,
  Copy,
  Check,
  Linkedin,
  Twitter,
  Mail,
  MessageCircle,
  TrendingUp,
  Clock,
  CheckCircle2,
  ArrowRight,
  Shield,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { createClient } from "@/lib/supabase/client";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReferralSummary {
  total_earned: number;
  pending: number;
  paid_out: number;
}

interface Referral {
  id: string;
  referral_code: string;
  referral_url: string;
  reward_type: "commission" | "free_month";
  status: string;
  commission_rate_pct: number;
  months_remaining: number;
  subscription_amount: number | null;
  commission_amount: number | null;
  referred_at: string;
  converted_at: string | null;
}

interface MeResponse {
  referrals: Referral[];
  summary: ReferralSummary;
}

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const colours: Record<string, string> = {
    pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    signed_up: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
    converted: "bg-green-500/10 text-green-400 border-green-500/20",
    paid_out: "bg-teal-500/10 text-teal-400 border-teal-500/20",
    expired: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };
  const cls = colours[status] ?? "bg-slate-500/10 text-slate-400 border-slate-500/20";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${cls}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

// ── Social share buttons ──────────────────────────────────────────────────────

function ShareButtons({ url }: { url: string }) {
  const encodedUrl = encodeURIComponent(url);
  const shareText = encodeURIComponent(
    "I use Varuflow to manage my business — worth checking out.",
  );

  const buttons = [
    {
      label: "LinkedIn",
      icon: <Linkedin className="h-4 w-4" />,
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`,
      colour: "bg-[#0077b5]/10 hover:bg-[#0077b5]/20 text-[#0077b5]",
    },
    {
      label: "X / Twitter",
      icon: <Twitter className="h-4 w-4" />,
      href: `https://twitter.com/intent/tweet?text=${shareText}&url=${encodedUrl}`,
      colour: "bg-slate-800 hover:bg-slate-700 text-slate-300",
    },
    {
      label: "WhatsApp",
      icon: <MessageCircle className="h-4 w-4" />,
      href: `https://wa.me/?text=${encodeURIComponent(`Check out Varuflow — great for wholesale businesses: ${url}`)}`,
      colour: "bg-[#25D366]/10 hover:bg-[#25D366]/20 text-[#25D366]",
    },
    {
      label: "Email",
      icon: <Mail className="h-4 w-4" />,
      href: `mailto:?subject=${encodeURIComponent("Try Varuflow — built for wholesalers")}&body=${encodeURIComponent(`I recommend Varuflow for your wholesale business: ${url}`)}`,
      colour: "bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400",
    },
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {buttons.map(({ label, icon, href, colour }) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={`flex items-center gap-1.5 rounded-lg border border-white/8 px-3 py-2 text-xs font-medium transition-colors ${colour}`}
        >
          {icon}
          {label}
        </a>
      ))}
    </div>
  );
}

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy to clipboard");
    }
  }

  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:border-indigo-500/40 hover:text-white"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

// ── Main page component ───────────────────────────────────────────────────────

export default function ReferralsPage() {
  const router = useRouter();
  const locale = useLocale();

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [data, setData] = useState<MeResponse | null>(null);
  const [activeReferral, setActiveReferral] = useState<Referral | null>(null);
  const [rewardType, setRewardType] = useState<"commission" | "free_month">("commission");

  // Load existing referrals
  const loadReferrals = useCallback(async () => {
    try {
      const supabase = createClient();
      if (!supabase) {
        router.push(`/${locale}/auth/login`);
        return;
      }
      const { data: user } = await supabase.auth.getUser();
      if (!user.user) {
        router.push(`/${locale}/auth/login`);
        return;
      }

      const res = await apiClient.get<MeResponse>("/api/referrals/me");
      setData(res);
      // Pick most recent active referral
      if (res.referrals.length > 0) {
        const active = res.referrals.find((r) => r.status !== "expired") ?? res.referrals[0];
        setActiveReferral(active);
        setRewardType(active.reward_type);
      }
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 401) {
        router.push(`/${locale}/auth/login`);
      } else if (status !== 404) {
        toast.error("Failed to load referrals");
      }
    } finally {
      setLoading(false);
    }
  }, [router, locale]);

  useEffect(() => {
    loadReferrals();
  }, [loadReferrals]);

  async function generateReferral(type: "commission" | "free_month") {
    setGenerating(true);
    try {
      const res = await apiClient.post<Referral>("/api/referrals/generate", { reward_type: type });
      setActiveReferral(res);
      setRewardType(type);
      await loadReferrals();
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 429) {
        toast.error("Daily generation limit reached. Try again tomorrow.");
      } else {
        toast.error("Failed to generate referral link");
      }
    } finally {
      setGenerating(false);
    }
  }

  // ── Skeleton ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <div className="mb-8 h-8 w-48 animate-pulse rounded bg-white/8" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-2xl bg-white/4" />
          ))}
        </div>
      </div>
    );
  }

  const summary = data?.summary ?? { total_earned: 0, pending: 0, paid_out: 0 };
  const referrals = data?.referrals ?? [];

  const referralUrl = activeReferral?.referral_url ?? `${BASE}/?ref=YOUR-CODE`;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 space-y-8">

      {/* Header */}
      <div>
        <h1 className="vf-text-1 text-2xl font-extrabold tracking-tight">
          Refer &amp; Earn
        </h1>
        <p className="vf-text-2 mt-1 text-sm">
          When a business you refer becomes a paying customer, you earn 20% of their
          monthly subscription for 12 months — or take one free month as credit.
        </p>
      </div>

      {/* Earnings summary */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Total earned", value: `${summary.total_earned.toLocaleString("sv-SE")} SEK`, icon: <TrendingUp className="h-4 w-4 text-green-400" /> },
          { label: "Pending", value: `${summary.pending.toLocaleString("sv-SE")} SEK`, icon: <Clock className="h-4 w-4 text-yellow-400" /> },
          { label: "Paid out", value: `${summary.paid_out.toLocaleString("sv-SE")} SEK`, icon: <CheckCircle2 className="h-4 w-4 text-teal-400" /> },
        ].map(({ label, value, icon }) => (
          <div
            key={label}
            className="rounded-2xl border border-white/8 bg-white/4 p-4"
          >
            <div className="mb-1 flex items-center gap-1.5">{icon}<span className="text-xs text-slate-400">{label}</span></div>
            <p className="vf-text-1 text-lg font-bold">{value}</p>
          </div>
        ))}
      </div>

      {/* Reward type picker */}
      <div className="rounded-2xl border border-white/8 bg-white/4 p-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Choose your reward
        </p>
        <div className="flex flex-wrap gap-3">
          {(["commission", "free_month"] as const).map((type) => (
            <button
              key={type}
              disabled={generating}
              onClick={() => generateReferral(type)}
              className={`flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-all ${
                rewardType === type && activeReferral
                  ? "border-indigo-500/40 bg-indigo-500/20 text-white"
                  : "border-white/10 bg-white/4 text-slate-300 hover:border-indigo-500/20 hover:text-white"
              }`}
            >
              {type === "commission" ? "💰 Commission (20% × 12 mo)" : "🎁 Free month credit"}
              {generating && rewardType === type && (
                <span className="ml-1 h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
              )}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Selecting a reward generates your personal referral link.
        </p>
      </div>

      {/* Referral link */}
      {activeReferral && (
        <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/8 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-indigo-400" />
            <p className="text-sm font-semibold text-white">Your referral link</p>
          </div>

          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/4 px-3 py-2">
            <code className="flex-1 truncate text-xs text-indigo-300">{referralUrl}</code>
            <CopyButton text={referralUrl} />
          </div>

          <ShareButtons url={referralUrl} />

          <p className="text-xs text-slate-400">
            When someone signs up via your link and upgrades to a paid plan, you earn{" "}
            {rewardType === "commission"
              ? "20% of their monthly subscription for 12 months."
              : "one free month added to your next invoice."}
          </p>
        </div>
      )}

      {/* No referral yet — prompt to generate */}
      {!activeReferral && !loading && (
        <div className="rounded-2xl border border-dashed border-white/12 p-8 text-center">
          <Link2 className="mx-auto mb-3 h-8 w-8 text-slate-600" />
          <p className="vf-text-1 mb-1 font-semibold">No referral link yet</p>
          <p className="vf-text-2 mb-4 text-sm">
            Choose a reward type above to generate your personal referral link.
          </p>
          <button
            onClick={() => generateReferral("commission")}
            disabled={generating}
            className="vf-btn rounded-xl px-5 py-2.5 text-sm font-semibold"
          >
            {generating ? "Generating…" : "Generate link →"}
          </button>
        </div>
      )}

      {/* Referrals table */}
      <div>
        <h2 className="vf-text-1 mb-4 text-base font-bold">Your referrals</h2>

        {referrals.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/8 py-10 text-center">
            <p className="vf-text-2 text-sm">No referrals yet. Share your link to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/8">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/8 bg-white/4 text-left text-xs text-slate-400">
                  <th className="px-4 py-2.5">Referred at</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Type</th>
                  <th className="px-4 py-2.5 text-right">Mo. left</th>
                  <th className="px-4 py-2.5 text-right">Earned</th>
                </tr>
              </thead>
              <tbody>
                {referrals.map((r) => (
                  <tr key={r.id} className="border-b border-white/6 last:border-0">
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {new Date(r.referred_at).toLocaleDateString("en-GB", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {r.reward_type === "commission" ? "Commission" : "Free month"}
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-slate-400">
                      {r.months_remaining}
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-white">
                      {r.commission_amount != null
                        ? `${r.commission_amount.toLocaleString("sv-SE")} SEK`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* How it works */}
      <div className="rounded-2xl border border-white/8 bg-white/4 p-6">
        <h2 className="vf-text-1 mb-5 text-base font-bold">How it works</h2>
        <ol className="space-y-4">
          {[
            { step: "1", text: "Generate your personal referral link above." },
            { step: "2", text: "Share it with business owners you think would benefit from Varuflow." },
            { step: "3", text: "When they sign up and upgrade to a paid plan within 30 days, the referral is confirmed." },
            {
              step: "4",
              text:
                rewardType === "commission"
                  ? "You earn 20% of their monthly subscription for 12 months, paid on the 1st of each month."
                  : "A free month credit is applied to your next Varuflow invoice.",
            },
          ].map(({ step, text }) => (
            <li key={step} className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                {step}
              </span>
              <p className="vf-text-2 text-sm leading-relaxed">{text}</p>
            </li>
          ))}
        </ol>
      </div>

      {/* Anti-fraud notice */}
      <div className="flex items-start gap-2 rounded-xl border border-white/6 bg-white/2 p-4">
        <Shield className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
        <p className="text-xs text-slate-500">
          Referrals are subject to review. Self-referrals, coordinated abuse, and referrals
          from connected organisations are not eligible for rewards. Commissions are held for
          30 days before payout to account for refunds and chargebacks.
        </p>
      </div>
    </div>
  );
}
