"use client";

/**
 * Settings → Commissions (Item 32)
 *
 * Owner/admin UI for managing per-staff commission rules. The page is
 * intentionally light — it lists existing rules and lets the operator
 * create or soft-disable them. Run management (creating / locking /
 * exporting a period run) lives on the analytics page.
 *
 * Wires: GET/POST/DELETE /api/commissions/rules
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Percent, Loader2, Trash2, Plus } from "lucide-react";

import { api } from "@/lib/api-client";

interface CommissionRule {
  id: string;
  staff_id: string;
  rule_type: "flat" | "pct" | "tiered";
  value: string;
  applies_to: string;
  min_threshold: string | null;
  is_active: boolean;
}

interface Staff {
  id: string;
  name: string;
}

export default function CommissionsSettingsPage() {
  const t = useTranslations("commissions");
  const [rules, setRules] = useState<CommissionRule[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Create-form state
  const [staffId, setStaffId] = useState("");
  const [ruleType, setRuleType] = useState<"flat" | "pct" | "tiered">("pct");
  const [value, setValue] = useState("");
  const [appliesTo, setAppliesTo] = useState("all");
  const [minThreshold, setMinThreshold] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rulesRes, staffRes] = await Promise.all([
        api.get<CommissionRule[]>("/api/commissions/rules"),
        api.get<Staff[]>("/api/staff").catch(() => [] as Staff[]),
      ]);
      setRules(rulesRes);
      setStaff(staffRes);
    } catch (err) {
      toast.error(t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const createRule = async () => {
    if (!staffId || !value) {
      toast.error(t("missing_fields"));
      return;
    }
    setSaving(true);
    try {
      await api.post("/api/commissions/rules", {
        staff_id: staffId,
        rule_type: ruleType,
        value,
        applies_to: appliesTo,
        min_threshold: minThreshold || null,
      });
      toast.success(t("rule_created"));
      setStaffId("");
      setValue("");
      setMinThreshold("");
      await load();
    } catch (err) {
      toast.error(t("create_failed"));
    } finally {
      setSaving(false);
    }
  };

  const disableRule = async (id: string) => {
    try {
      await api.delete(`/api/commissions/rules/${id}`);
      toast.success(t("rule_disabled"));
      await load();
    } catch (err) {
      toast.error(t("disable_failed"));
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
        <Percent className="h-6 w-6" />
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
      </div>
      <p className="text-sm text-muted-foreground">{t("description")}</p>

      {/* Create rule */}
      <div className="rounded-lg border p-4 space-y-3">
        <h2 className="font-medium">{t("create_rule")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <select
            value={staffId}
            onChange={(e) => setStaffId(e.target.value)}
            className="rounded border px-2 py-1 text-sm"
          >
            <option value="">{t("pick_staff")}</option>
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            value={ruleType}
            onChange={(e) => setRuleType(e.target.value as "flat" | "pct" | "tiered")}
            className="rounded border px-2 py-1 text-sm"
          >
            <option value="pct">{t("type_pct")}</option>
            <option value="flat">{t("type_flat")}</option>
            <option value="tiered">{t("type_tiered")}</option>
          </select>
          <input
            type="number"
            step="0.01"
            placeholder={t("value_placeholder")}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="rounded border px-2 py-1 text-sm"
          />
          <select
            value={appliesTo}
            onChange={(e) => setAppliesTo(e.target.value)}
            className="rounded border px-2 py-1 text-sm"
          >
            <option value="all">{t("applies_all")}</option>
            <option value="service">{t("applies_service")}</option>
            <option value="sale">{t("applies_sale")}</option>
            <option value="invoice">{t("applies_invoice")}</option>
          </select>
          {ruleType === "tiered" ? (
            <input
              type="number"
              step="0.01"
              placeholder={t("threshold_placeholder")}
              value={minThreshold}
              onChange={(e) => setMinThreshold(e.target.value)}
              className="rounded border px-2 py-1 text-sm"
            />
          ) : (
            <div />
          )}
        </div>
        <button
          onClick={createRule}
          disabled={saving}
          className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          {t("create")}
        </button>
      </div>

      {/* Rules table */}
      <div className="rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="text-left p-2">{t("col_staff")}</th>
              <th className="text-left p-2">{t("col_type")}</th>
              <th className="text-right p-2">{t("col_value")}</th>
              <th className="text-left p-2">{t("col_applies_to")}</th>
              <th className="text-right p-2">{t("col_threshold")}</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {rules.length === 0 && (
              <tr>
                <td colSpan={6} className="p-4 text-center text-muted-foreground">
                  {t("no_rules")}
                </td>
              </tr>
            )}
            {rules.map((r) => {
              const s = staff.find((x) => x.id === r.staff_id);
              return (
                <tr key={r.id} className="border-t">
                  <td className="p-2">{s ? s.name : r.staff_id.slice(0, 8)}</td>
                  <td className="p-2">{t(`type_${r.rule_type}`)}</td>
                  <td className="p-2 text-right">{r.value}</td>
                  <td className="p-2">{r.applies_to}</td>
                  <td className="p-2 text-right">{r.min_threshold ?? "—"}</td>
                  <td className="p-2 text-right">
                    <button
                      onClick={() => disableRule(r.id)}
                      className="text-destructive hover:underline inline-flex items-center gap-1"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {t("disable")}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
