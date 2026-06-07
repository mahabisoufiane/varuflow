"use client";

import { useEffect, useRef, useState } from "react";
import { api, getActiveBranchOrgId, setActiveBranchOrgId } from "@/lib/api-client";
import { Globe, Check, ChevronDown, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Branch {
  id: string;
  name: string;
  country_code: string | null;
  entity_type: string;
  parent_org_id: string | null;
  base_currency: string;
  plan: string;
}

/** Country flag emoji from ISO-3166-1 alpha-2 code. */
function countryFlag(code: string | null): string {
  if (!code || code.length !== 2) return "🏢";
  const offset = 0x1f1e6 - 65;
  return String.fromCodePoint(code.charCodeAt(0) + offset, code.charCodeAt(1) + offset);
}

export function WorkspaceSwitcher() {
  const [branches, setBranches]     = useState<Branch[]>([]);
  const [activeId, setActiveId]     = useState<string | null>(null);
  const [open, setOpen]             = useState(false);
  const [loading, setLoading]       = useState(true);
  const dropdownRef                 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setActiveId(getActiveBranchOrgId());
    api.get<Branch[]>("/api/multi-entity/branches")
      .then((data) => setBranches(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Only show when there are multiple workspaces to switch between
  if (loading || branches.length <= 1) return null;

  const active = branches.find((b) => b.id === activeId) ?? branches[0];

  function switchTo(branch: Branch) {
    const newId = branch.id === branches[0]?.id && !activeId ? null : branch.id;
    setActiveBranchOrgId(newId);
    setActiveId(newId);
    setOpen(false);
    // Reload so all data re-fetches with the new org context header
    window.location.reload();
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs font-medium transition-all",
          "vf-text-m hover:vf-text-2 vf-btn-ghost h-9 border border-[var(--vf-border)]"
        )}
        title="Switch workspace"
      >
        <Globe className="h-3.5 w-3.5 shrink-0" />
        <span className="hidden xl:inline max-w-[120px] truncate">
          {countryFlag(active.country_code)} {active.name}
        </span>
        <ChevronDown className={cn("h-3 w-3 shrink-0 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-1.5 w-64 rounded-xl p-1 shadow-lg"
          style={{
            background: "var(--vf-bg-elevated)",
            border: "1px solid var(--vf-border)",
          }}
        >
          <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider vf-text-m">
            Workspaces
          </p>
          {branches.map((branch) => {
            const isActive =
              branch.id === activeId ||
              (!activeId && branch.id === branches[0]?.id);
            return (
              <button
                key={branch.id}
                onClick={() => switchTo(branch)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors",
                  isActive
                    ? "bg-indigo-500/[0.10] text-indigo-500"
                    : "vf-text-2 hover:bg-[var(--vf-hover)]"
                )}
              >
                <span className="text-base leading-none">
                  {countryFlag(branch.country_code)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-[13px] font-medium">{branch.name}</p>
                  <p className="text-[10px] vf-text-m">
                    {branch.country_code ?? "Global"} · {branch.base_currency} · {branch.plan}
                  </p>
                </div>
                {isActive && <Check className="h-3.5 w-3.5 shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
