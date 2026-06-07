"use client";

import { useLocale } from "next-intl";
import { Building2, BarChart3, ArrowLeftRight, GitBranch, Globe, Plus, Check } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import styles from "./page.module.scss";

const FEATURES = [
  {
    icon: <Building2 className="h-8 w-8" />,
    title: "Subsidiaries",
    description: "Manage your group structure — create subsidiary orgs, set legal names, and assign reporting currencies.",
    href: "multi-entity/subsidiaries",
    color: "bg-blue-50 text-blue-600",
  },
  {
    icon: <BarChart3 className="h-8 w-8" />,
    title: "Consolidated Reports",
    description: "View group P&L across all entities with automatic intercompany eliminations.",
    href: "multi-entity/consolidated",
    color: "bg-green-50 text-green-600",
  },
  {
    icon: <ArrowLeftRight className="h-8 w-8" />,
    title: "Intercompany Transfers",
    description: "Record stock, cash, and service transfers between entities at arm's-length transfer prices.",
    href: "multi-entity/intercompany",
    color: "bg-purple-50 text-purple-600",
  },
  {
    icon: <GitBranch className="h-8 w-8" />,
    title: "Franchise",
    description: "Onboard franchisees, run royalty billing, and push your product catalogue across the network.",
    href: "franchise",
    color: "bg-amber-50 text-amber-600",
  },
];

const COUNTRY_OPTIONS = [
  { code: "SE", label: "Sweden", currency: "SEK" },
  { code: "NO", label: "Norway", currency: "NOK" },
  { code: "DK", label: "Denmark", currency: "DKK" },
  { code: "FI", label: "Finland", currency: "EUR" },
  { code: "DE", label: "Germany", currency: "EUR" },
  { code: "NL", label: "Netherlands", currency: "EUR" },
  { code: "GB", label: "United Kingdom", currency: "GBP" },
  { code: "US", label: "United States", currency: "USD" },
  { code: "AE", label: "UAE", currency: "AED" },
  { code: "SA", label: "Saudi Arabia", currency: "SAR" },
];

function countryFlag(code: string): string {
  const offset = 0x1f1e6 - 65;
  return String.fromCodePoint(code.charCodeAt(0) + offset, code.charCodeAt(1) + offset);
}

function AddWorkspaceForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen]         = useState(false);
  const [name, setName]         = useState("");
  const [countryCode, setCountryCode] = useState("NO");
  const [currency, setCurrency] = useState("NOK");
  const [saving, setSaving]     = useState(false);

  function handleCountryChange(code: string) {
    setCountryCode(code);
    const opt = COUNTRY_OPTIONS.find((c) => c.code === code);
    if (opt) setCurrency(opt.currency);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/api/multi-entity/branches", {
        name: name || `${COUNTRY_OPTIONS.find(c => c.code === countryCode)?.label ?? countryCode} Workspace`,
        country_code: countryCode,
        base_currency: currency,
      });
      toast.success("Country workspace created — workspace switcher is now active");
      setOpen(false);
      setName("");
      onCreated();
      // Reload so WorkspaceSwitcher picks up the new branch
      window.location.reload();
    } catch (e: unknown) {
      toast.error((e as Error).message ?? "Failed to create workspace");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className={"flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-white transition-colors " + styles.headerBadge}>
        <Plus className="h-4 w-4" />
        Add Country Workspace
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={"rounded-2xl p-5 space-y-4 " + styles.elevatedCard}>
      <div className="flex items-center gap-2">
        <Globe className="h-5 w-5 text-indigo-400" />
        <h3 className="text-[14px] font-semibold vf-text-1">New Country Workspace</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-1 space-y-1">
          <label className="text-xs font-medium vf-text-2">Country</label>
          <select
            value={countryCode}
            onChange={(e) => handleCountryChange(e.target.value)}
            className="vf-input w-full">
            {COUNTRY_OPTIONS.map((c) => (
              <option key={c.code} value={c.code}>
                {countryFlag(c.code)} {c.label}
              </option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-1 space-y-1">
          <label className="text-xs font-medium vf-text-2">Workspace name</label>
          <input
            type="text"
            placeholder={`${COUNTRY_OPTIONS.find(c => c.code === countryCode)?.label ?? countryCode} Workspace`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="vf-input w-full" />
        </div>
        <div className="sm:col-span-1 space-y-1">
          <label className="text-xs font-medium vf-text-2">Base currency</label>
          <input
            type="text"
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            maxLength={3}
            className="vf-input w-full uppercase" />
        </div>
      </div>

      <p className="text-xs vf-text-m">
        A new organization will be created for this country. You will automatically have owner access to both workspaces. Use the globe icon in the top bar to switch between them.
      </p>

      <div className="flex items-center gap-3">
        <button type="submit" disabled={saving} className="vf-btn disabled:opacity-50 flex items-center gap-2">
          {saving ? "Creating…" : (<><Check className="h-4 w-4" /> Create workspace</>)}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-sm vf-text-m hover:vf-text-2 transition-colors">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function MultiEntityHubPage() {
  const locale = useLocale();

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold vf-text-1">Multi-Entity & Franchise</h1>
          <p className="mt-1 text-sm vf-text-m">
            Manage subsidiary branches, consolidated group reporting, intercompany accounting, and franchise networks.
          </p>
        </div>
      </div>

      {/* Country workspace creation */}
      <div className="space-y-3">
        <div>
          <h2 className="text-[14px] font-semibold vf-text-1">Country Workspaces</h2>
          <p className="text-xs vf-text-m mt-0.5">Expand to a new country — each workspace has its own team, rules, and currency.</p>
        </div>
        <AddWorkspaceForm onCreated={() => {}} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {FEATURES.map((f) => (
          <a
            key={f.href}
            href={`/${locale}/${f.href}`}
            className={"group flex flex-col gap-4 rounded-2xl p-6 transition-all " + styles.elevatedCard}
          >
            <div className={`flex h-14 w-14 items-center justify-center rounded-xl ${f.color} transition-transform group-hover:scale-105`}>
              {f.icon}
            </div>
            <div>
              <h2 className="text-base font-semibold vf-text-1">{f.title}</h2>
              <p className="mt-1 text-sm vf-text-m">{f.description}</p>
            </div>
            <span className="mt-auto text-sm font-medium text-indigo-400 group-hover:underline">Open →</span>
          </a>
        ))}
      </div>
    </div>
  );
}
