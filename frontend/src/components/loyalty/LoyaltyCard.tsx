"use client";

/**
 * Loyalty card (Item 35).
 *
 * Customer-facing balance + tier summary. Used on the customer list
 * row and the customer detail page. Fetches the account lazily so
 * admins browsing the customer list don't hammer ``/api/loyalty``
 * for every row — the caller must render this component only when
 * a card is actually visible.
 */
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Trophy, Loader2 } from "lucide-react";

import { api } from "@/lib/api-client";

interface LoyaltyAccount {
  id: string;
  customer_id: string;
  points_balance: number;
  lifetime_points: number;
  tier: string;
  created_at: string;
}

interface Tier {
  name: string;
  threshold: number;
}

interface Props {
  customerId: string;
}

function tierColor(tier: string): string {
  switch (tier) {
    case "platinum":
      return "bg-slate-700 text-slate-100";
    case "gold":
      return "bg-amber-500 text-amber-950";
    case "silver":
      return "bg-zinc-300 text-zinc-900";
    default:
      return "bg-orange-700 text-orange-50";
  }
}

export function LoyaltyCard({ customerId }: Props) {
  const t = useTranslations("loyalty");
  const [account, setAccount] = useState<LoyaltyAccount | null>(null);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const [acc, tierRes] = await Promise.all([
          api.get<LoyaltyAccount>(`/api/loyalty/accounts/${customerId}`),
          api.get<Tier[]>("/api/loyalty/tiers").catch(() => [] as Tier[]),
        ]);
        if (!cancelled) {
          setAccount(acc);
          setTiers(tierRes);
        }
      } catch {
        if (!cancelled) setAccount(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-md border bg-card p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("loading")}
      </div>
    );
  }

  if (!account) {
    return (
      <div className="rounded-md border bg-card p-4 text-sm text-muted-foreground">
        {t("no_account")}
      </div>
    );
  }

  const currentIdx = tiers.findIndex((tier) => tier.name === account.tier);
  const next = currentIdx >= 0 && currentIdx < tiers.length - 1 ? tiers[currentIdx + 1] : null;
  const toNext = next ? Math.max(0, next.threshold - account.lifetime_points) : 0;

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <Trophy className="h-5 w-5 text-primary" />
        <h3 className="text-base font-medium">{t("title")}</h3>
        <span
          className={`ml-auto rounded-full px-3 py-1 text-xs font-semibold uppercase ${tierColor(
            account.tier
          )}`}
        >
          {t(`tier.${account.tier}` as "tier.bronze")}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">{t("balance")}</div>
          <div className="text-2xl font-semibold tabular-nums">
            {account.points_balance.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">{t("lifetime")}</div>
          <div className="text-2xl font-semibold tabular-nums">
            {account.lifetime_points.toLocaleString()}
          </div>
        </div>
      </div>
      {next && (
        <div className="mt-4 text-xs text-muted-foreground">
          {t("next_tier", { points: toNext.toLocaleString(), tier: t(`tier.${next.name}` as "tier.silver") })}
        </div>
      )}
    </div>
  );
}
