"use client";
// frontend/src/app/[locale]/(app)/partner/page.tsx
// Partner dashboard — accounting firm commission tracking.

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { useRouter, Link } from "@/i18n/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import {
  Copy,
  Check,
  Download,
  ExternalLink,
  TrendingUp,
  Users,
  DollarSign,
  Clock,
} from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

// ── Types ──────────────────────────────────────────────────────────────────

interface PartnerData {
  id: string;
  firm_name: string;
  contact_name: string;
  contact_email: string;
  status: "pending" | "approved" | "active" | "paused" | "terminated";
  referral_code: string;
  commission_rate_pct: number;
  created_at: string;
}

interface DashboardStats {
  total_referrals: number;
  conversions: number;
  commission_earned: number;
  commission_pending: number;
  commission_paid: number;
}

interface DashboardResponse {
  partner: PartnerData;
  stats: DashboardStats;
}

interface Referral {
  id: string;
  status: string;
  referred_org_id: string | null;
  months_remaining: number;
  commission_amount: number | null;
  converted_at: string | null;
  created_at: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { label: string; cls: string }> = {
    pending:    { label: "Pending",    cls: "rounded-full bg-yellow-500/15 px-2.5 py-0.5 text-xs font-semibold text-yellow-400" },
    approved:   { label: "Approved",   cls: "rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-semibold text-indigo-400" },
    active:     { label: "Active",     cls: "rounded-full bg-green-500/15 px-2.5 py-0.5 text-xs font-semibold text-green-400" },
    paused:     { label: "Paused",     cls: "rounded-full bg-slate-500/15 px-2.5 py-0.5 text-xs font-semibold text-slate-400" },
    terminated: { label: "Terminated", cls: "rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-semibold text-red-400" },
  };
  const s = cfg[status] ?? cfg.pending;
  return <span className={s.cls}>{s.label}</span>;
}

function ReferralStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending:   "text-yellow-400",
    clicked:   "text-blue-400",
    converted: "text-green-400",
    paid_out:  "text-slate-400",
    expired:   "text-red-400",
  };
  const cls = map[status] ?? "text-slate-400";
  return (
    <span className={`${cls} text-xs font-semibold capitalize`}>{status.replace(/_/g, " ")}</span>
  );
}

const ASSETS = [
  { title: "Email Template", desc: "Ready-to-send client intro email", file: "email-template.html" },
  { title: "Banner 1200×628", desc: "Social media cover image", file: "banner-1200x628.png" },
  { title: "One-pager PDF", desc: "Printable Varuflow overview", file: "one-pager.pdf" },
  { title: "Partner Badge", desc: "Add to your website footer", file: "partner-badge.svg" },
];

// ── Component ──────────────────────────────────────────────────────────────

export default function PartnerDashboardPage() {
  const locale = useLocale();
  const router = useRouter();

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const dashboard = await api.get<DashboardResponse>("/api/partners/me");
        setData(dashboard);
        try {
          const refs = await api.get<Referral[]>("/api/partners/me/referrals");
          setReferrals(refs);
        } catch {
          // Referrals are non-critical — show dashboard without them
        }
      } catch (err: unknown) {
        const status = (err as { status?: number }).status;
        if (status === 401) {
          router.push(`/${locale}/auth/login`);
        } else if (status === 404) {
          setNotFound(true);
        } else {
          toast.error("Could not load partner dashboard. Please try again.");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [locale, router]);

  async function copyLink() {
    if (!data) return;
    const url = `${BASE}/ref/${data.partner.referral_code}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy to clipboard.");
    }
  }

  // ── Loading ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  // ── No partner account ────────────────────────────────────────────────────

  if (notFound) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10">
          <Users className="h-7 w-7 text-indigo-400" />
        </div>
        <h1 className="vf-text-1 text-xl font-bold">No partner account found</h1>
        <p className="vf-text-2 max-w-sm text-sm">
          You haven&apos;t applied to the partner program yet. Apply in 2 minutes and we&apos;ll
          review within 1 business day.
        </p>
        <Link
          href="/partners"
          className="vf-btn inline-flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-semibold"
        >
          Apply to partner program
        </Link>
      </div>
    );
  }

  if (!data) return null;

  const { partner, stats } = data;
  const referralUrl = `${BASE}/ref/${partner.referral_code}`;

  const STAT_CARDS = [
    {
      label: "Total Referrals",
      value: String(stats.total_referrals),
      icon: Users,
      color: "text-indigo-400 bg-indigo-500/10",
    },
    {
      label: "Conversions",
      value: String(stats.conversions),
      icon: TrendingUp,
      color: "text-green-400 bg-green-500/10",
    },
    {
      label: "Earned (SEK)",
      value: `${fmt(stats.commission_earned)} kr`,
      icon: DollarSign,
      color: "text-violet-400 bg-violet-500/10",
    },
    {
      label: "Pending (SEK)",
      value: `${fmt(stats.commission_pending)} kr`,
      icon: Clock,
      color: "text-amber-400 bg-amber-500/10",
    },
  ];

  return (
    <div className="space-y-6">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="vf-text-1 text-xl font-bold tracking-tight">Partner Dashboard</h1>
          <div className="mt-1 flex items-center gap-2">
            <p className="vf-text-2 text-sm">{partner.firm_name}</p>
            <StatusBadge status={partner.status} />
          </div>
        </div>
        <a
          href="/downloads/partner-pack.pdf"
          download
          className="vf-btn-ghost inline-flex items-center gap-1.5 text-xs"
        >
          <Download className="h-3.5 w-3.5" />
          Download assets
        </a>
      </div>

      {/* ── Stats ────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {STAT_CARDS.map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="rounded-xl border border-white/8 bg-white/4 p-4"
          >
            <div
              className={`mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl ${color}`}
            >
              <Icon className="h-4 w-4" />
            </div>
            <p className="vf-text-2 mb-1 text-[10px] font-semibold uppercase tracking-wide">
              {label}
            </p>
            <p className="vf-text-1 text-xl font-bold tabular-nums">{value}</p>
          </div>
        ))}
      </div>

      {/* ── Referral link ────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/6 p-5">
        <p className="vf-text-1 mb-1 text-sm font-semibold">Your referral link</p>
        <p className="vf-text-2 mb-3 text-xs">
          Share this link with clients. Commissions are tracked automatically.
        </p>
        <div className="flex items-center gap-2">
          <div
            className="flex-1 truncate rounded-lg border border-white/10 bg-[#090C12] px-3 py-2 font-mono text-xs text-slate-300"
          >
            {referralUrl}
          </div>
          <button
            onClick={copyLink}
            className="vf-btn-ghost flex items-center gap-1.5 text-xs"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-green-400" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy
              </>
            )}
          </button>
          <a
            href={referralUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="vf-btn-ghost flex items-center gap-1.5 text-xs"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      {/* ── Referrals table ──────────────────────────────────────────────── */}
      <div>
        <h2 className="vf-text-1 mb-3 text-base font-semibold">
          Referrals
          <span className="vf-text-2 ml-2 text-xs font-normal">
            ({referrals.length})
          </span>
        </h2>
        {referrals.length === 0 ? (
          <div
            className="rounded-xl px-6 py-12 text-center"
            style={{ border: "1px dashed rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.02)" }}
          >
            <p className="vf-text-2 text-sm">No referrals yet. Share your link to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-white/8">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/8">
                  {["Date", "Status", "Org", "Months Left", "Commission (SEK)"].map((h) => (
                    <th
                      key={h}
                      className="vf-text-2 px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {referrals.map((ref) => (
                  <tr
                    key={ref.id}
                    className="border-b border-white/6 transition-colors last:border-0 hover:bg-white/4"
                  >
                    <td className="vf-text-2 px-4 py-3 text-xs tabular-nums">
                      {ref.created_at.slice(0, 10)}
                    </td>
                    <td className="px-4 py-3">
                      <ReferralStatusBadge status={ref.status} />
                    </td>
                    <td className="vf-text-2 px-4 py-3 text-xs">
                      {ref.referred_org_id ? (
                        <span className="font-mono text-slate-400">{ref.referred_org_id.slice(0, 8)}…</span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="vf-text-1 px-4 py-3 text-xs tabular-nums">
                      {ref.months_remaining}
                    </td>
                    <td className="vf-text-1 px-4 py-3 text-xs tabular-nums">
                      {ref.commission_amount != null
                        ? `${fmt(ref.commission_amount)} kr`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Marketing assets ─────────────────────────────────────────────── */}
      <div>
        <h2 className="vf-text-1 mb-3 text-base font-semibold">Marketing assets</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ASSETS.map(({ title, desc, file }) => (
            <div
              key={file}
              className="flex flex-col gap-3 rounded-xl border border-white/8 bg-white/4 p-4"
            >
              <div>
                <p className="vf-text-1 text-sm font-semibold">{title}</p>
                <p className="vf-text-2 mt-0.5 text-xs">{desc}</p>
              </div>
              <a
                href={`/downloads/partner/${file}`}
                download
                className="vf-btn-ghost mt-auto inline-flex items-center gap-1.5 text-xs"
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
