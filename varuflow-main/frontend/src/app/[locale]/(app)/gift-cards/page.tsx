"use client";

/**
 * Gift Cards page (Item 33)
 *
 * Owner/staff UI for issuing, listing, redeeming, and checking
 * balance on gift cards. Bundles management has its own tab below.
 *
 * Wires: /api/gift-cards/{issue,redeem,by-code/{code}/balance,...}
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Gift, Loader2, Search, Plus, Ban, Tag } from "lucide-react";

import { api } from "@/lib/api-client";

interface GiftCard {
  id: string;
  code: string;
  initial_value: string;
  remaining_value: string;
  issued_to_customer_id: string | null;
  expires_at: string | null;
  status: "active" | "redeemed" | "expired" | "void";
}

interface Bundle {
  id: string;
  name: string;
  price: string;
  valid_days: number;
  services: string[];
  sessions_total: number;
  is_active: boolean;
}

export default function GiftCardsPage() {
  const t = useTranslations("giftCards");
  const [tab, setTab] = useState<"cards" | "bundles">("cards");
  const [cards, setCards] = useState<GiftCard[]>([]);
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Issue form
  const [issueValue, setIssueValue] = useState("");
  const [issueDays, setIssueDays] = useState("365");

  // Redeem / balance check form
  const [checkCode, setCheckCode] = useState("");
  const [redeemAmount, setRedeemAmount] = useState("");
  const [balanceInfo, setBalanceInfo] = useState<{
    code: string;
    remaining_value: string;
    status: string;
    is_expired: boolean;
  } | null>(null);

  // Bundle form
  const [bundleName, setBundleName] = useState("");
  const [bundlePrice, setBundlePrice] = useState("");
  const [bundleSessions, setBundleSessions] = useState("5");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cardsRes, bundlesRes] = await Promise.all([
        api.get<GiftCard[]>("/api/gift-cards"),
        api.get<Bundle[]>("/api/gift-cards/bundles"),
      ]);
      setCards(cardsRes);
      setBundles(bundlesRes);
    } catch (err) {
      toast.error(t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const issueCard = async () => {
    if (!issueValue) {
      toast.error(t("missing_value"));
      return;
    }
    setSaving(true);
    try {
      const card = await api.post<GiftCard>("/api/gift-cards/issue", {
        initial_value: issueValue,
        valid_days: parseInt(issueDays, 10) || 365,
      });
      toast.success(t("issued", { code: card.code }));
      setIssueValue("");
      await load();
    } catch {
      toast.error(t("issue_failed"));
    } finally {
      setSaving(false);
    }
  };

  const checkBalance = async () => {
    if (!checkCode) return;
    try {
      const info = await api.get<typeof balanceInfo>(
        `/api/gift-cards/by-code/${encodeURIComponent(checkCode)}/balance`,
      );
      setBalanceInfo(info);
    } catch {
      setBalanceInfo(null);
      toast.error(t("card_not_found"));
    }
  };

  const redeem = async () => {
    if (!checkCode || !redeemAmount) {
      toast.error(t("missing_fields"));
      return;
    }
    try {
      const res = await api.post<{ applied: string; remaining_balance: string; shortfall: string }>(
        "/api/gift-cards/redeem",
        { code: checkCode, amount: redeemAmount },
      );
      toast.success(t("redeemed", { applied: res.applied, remaining: res.remaining_balance }));
      setRedeemAmount("");
      await checkBalance();
      await load();
    } catch {
      toast.error(t("redeem_failed"));
    }
  };

  const voidCard = async (id: string) => {
    try {
      await api.post(`/api/gift-cards/${id}/void`, {});
      toast.success(t("voided"));
      await load();
    } catch {
      toast.error(t("void_failed"));
    }
  };

  const createBundle = async () => {
    if (!bundleName || !bundlePrice) {
      toast.error(t("missing_fields"));
      return;
    }
    try {
      await api.post("/api/gift-cards/bundles", {
        name: bundleName,
        price: bundlePrice,
        valid_days: 365,
        services: [],
        sessions_total: parseInt(bundleSessions, 10) || 5,
      });
      toast.success(t("bundle_created"));
      setBundleName("");
      setBundlePrice("");
      await load();
    } catch {
      toast.error(t("bundle_create_failed"));
    }
  };

  const deactivateBundle = async (id: string) => {
    try {
      await api.delete(`/api/gift-cards/bundles/${id}`);
      toast.success(t("bundle_deactivated"));
      await load();
    } catch {
      toast.error(t("bundle_deactivate_failed"));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Gift className="h-6 w-6" />
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
      </div>

      <div className="flex gap-2 border-b">
        <button
          onClick={() => setTab("cards")}
          className={`px-3 py-2 text-sm ${tab === "cards" ? "border-b-2 border-primary font-medium" : "text-muted-foreground"}`}
        >
          {t("tab_cards")}
        </button>
        <button
          onClick={() => setTab("bundles")}
          className={`px-3 py-2 text-sm ${tab === "bundles" ? "border-b-2 border-primary font-medium" : "text-muted-foreground"}`}
        >
          {t("tab_bundles")}
        </button>
      </div>

      {tab === "cards" && (
        <div className="space-y-6">
          {/* Issue */}
          <div className="rounded-lg border p-4 space-y-3">
            <h2 className="font-medium">{t("issue_title")}</h2>
            <div className="flex gap-2">
              <input
                type="number"
                step="0.01"
                placeholder={t("value_placeholder")}
                value={issueValue}
                onChange={(e) => setIssueValue(e.target.value)}
                className="rounded border px-2 py-1 text-sm"
              />
              <input
                type="number"
                placeholder={t("valid_days_placeholder")}
                value={issueDays}
                onChange={(e) => setIssueDays(e.target.value)}
                className="rounded border px-2 py-1 text-sm w-32"
              />
              <button
                onClick={issueCard}
                disabled={saving}
                className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                {t("issue_action")}
              </button>
            </div>
          </div>

          {/* Balance & Redeem */}
          <div className="rounded-lg border p-4 space-y-3">
            <h2 className="font-medium">{t("balance_title")}</h2>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder={t("code_placeholder")}
                value={checkCode}
                onChange={(e) => setCheckCode(e.target.value.toUpperCase())}
                className="rounded border px-2 py-1 text-sm flex-1"
              />
              <button
                onClick={checkBalance}
                className="inline-flex items-center gap-1 rounded border px-3 py-1.5 text-sm"
              >
                <Search className="h-4 w-4" />
                {t("check")}
              </button>
            </div>
            {balanceInfo && (
              <div className="text-sm p-3 rounded bg-muted">
                <div>
                  {t("balance_label")}: <strong>{balanceInfo.remaining_value} SEK</strong>
                </div>
                <div>
                  {t("status_label")}: <strong>{t(`status_${balanceInfo.status}`)}</strong>
                  {balanceInfo.is_expired && <span className="text-destructive"> ({t("expired")})</span>}
                </div>
                <div className="flex gap-2 mt-2">
                  <input
                    type="number"
                    step="0.01"
                    placeholder={t("amount_placeholder")}
                    value={redeemAmount}
                    onChange={(e) => setRedeemAmount(e.target.value)}
                    className="rounded border px-2 py-1 text-sm"
                  />
                  <button
                    onClick={redeem}
                    disabled={balanceInfo.is_expired}
                    className="rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm disabled:opacity-50"
                  >
                    {t("redeem_action")}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Cards list */}
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left p-2">{t("col_code")}</th>
                  <th className="text-right p-2">{t("col_initial")}</th>
                  <th className="text-right p-2">{t("col_remaining")}</th>
                  <th className="text-left p-2">{t("col_status")}</th>
                  <th className="text-left p-2">{t("col_expires")}</th>
                  <th className="p-2" />
                </tr>
              </thead>
              <tbody>
                {cards.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-4 text-center text-muted-foreground">
                      {t("no_cards")}
                    </td>
                  </tr>
                )}
                {cards.map((c) => (
                  <tr key={c.id} className="border-t">
                    <td className="p-2 font-mono">{c.code}</td>
                    <td className="p-2 text-right">{c.initial_value}</td>
                    <td className="p-2 text-right">{c.remaining_value}</td>
                    <td className="p-2">{t(`status_${c.status}`)}</td>
                    <td className="p-2">{c.expires_at?.slice(0, 10) ?? "—"}</td>
                    <td className="p-2 text-right">
                      {c.status === "active" && (
                        <button
                          onClick={() => voidCard(c.id)}
                          className="inline-flex items-center gap-1 text-xs text-destructive hover:underline"
                        >
                          <Ban className="h-3.5 w-3.5" />
                          {t("void")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "bundles" && (
        <div className="space-y-6">
          <div className="rounded-lg border p-4 space-y-3">
            <h2 className="font-medium">{t("bundle_create_title")}</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <input
                placeholder={t("bundle_name_placeholder")}
                value={bundleName}
                onChange={(e) => setBundleName(e.target.value)}
                className="rounded border px-2 py-1 text-sm"
              />
              <input
                type="number"
                step="0.01"
                placeholder={t("bundle_price_placeholder")}
                value={bundlePrice}
                onChange={(e) => setBundlePrice(e.target.value)}
                className="rounded border px-2 py-1 text-sm"
              />
              <input
                type="number"
                placeholder={t("bundle_sessions_placeholder")}
                value={bundleSessions}
                onChange={(e) => setBundleSessions(e.target.value)}
                className="rounded border px-2 py-1 text-sm"
              />
              <button
                onClick={createBundle}
                className="inline-flex items-center justify-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
              >
                <Plus className="h-4 w-4" />
                {t("bundle_create")}
              </button>
            </div>
          </div>

          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left p-2">{t("col_name")}</th>
                  <th className="text-right p-2">{t("col_price")}</th>
                  <th className="text-right p-2">{t("col_sessions")}</th>
                  <th className="text-left p-2">{t("col_status")}</th>
                  <th className="p-2" />
                </tr>
              </thead>
              <tbody>
                {bundles.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-muted-foreground">
                      {t("no_bundles")}
                    </td>
                  </tr>
                )}
                {bundles.map((b) => (
                  <tr key={b.id} className="border-t">
                    <td className="p-2 inline-flex items-center gap-1">
                      <Tag className="h-3.5 w-3.5" />
                      {b.name}
                    </td>
                    <td className="p-2 text-right">{b.price}</td>
                    <td className="p-2 text-right">{b.sessions_total}</td>
                    <td className="p-2">
                      {b.is_active ? t("bundle_active") : t("bundle_inactive")}
                    </td>
                    <td className="p-2 text-right">
                      {b.is_active && (
                        <button
                          onClick={() => deactivateBundle(b.id)}
                          className="text-xs text-destructive hover:underline"
                        >
                          {t("bundle_deactivate")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
