"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { api } from "@/lib/api-client";
import {
  BarChart3, FileText, LayoutDashboard, Package,
  RefreshCw, Settings, ShoppingCart, Users, Search,
} from "lucide-react";

interface SearchResult {
  id: string;
  label: string;
  sub: string;
  href: string;
  type: "invoice" | "customer" | "product" | "booking";
}

interface SearchResponse {
  results: SearchResult[];
}

const NAV = [
  { label: "Dashboard", href: "/dashboard",  icon: LayoutDashboard },
  { label: "Analytics",  href: "/analytics",  icon: BarChart3        },
  { label: "Inventory",  href: "/inventory",  icon: Package          },
  { label: "Invoices",   href: "/invoices",   icon: FileText         },
  { label: "Recurring",  href: "/recurring",  icon: RefreshCw        },
  { label: "Cash Register", href: "/pos",     icon: ShoppingCart     },
  { label: "Customers",  href: "/customers",  icon: Users            },
  { label: "Settings",   href: "/settings",   icon: Settings         },
];

const TYPE_BADGE: Record<string, string> = {
  invoice:  "bg-emerald-500/10 text-emerald-400",
  customer: "bg-violet-500/10  text-violet-400",
  product:  "bg-blue-500/10    text-blue-400",
  booking:  "bg-amber-500/10   text-amber-400",
};

export default function CommandPalette() {
  const router     = useRouter();
  const locale     = useLocale();
  const [open, setOpen]         = useState(false);
  const [query, setQuery]       = useState("");
  const [results, setResults]   = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(o => !o);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const runSearch = useCallback(async (q: string) => {
    if (!q.trim() || q.length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const data = await api.get<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`);
      setResults(data.results ?? []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(query), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, runSearch]);

  function go(href: string, result?: SearchResult) {
    router.push(`/${locale}${href}`);
    setOpen(false);
    setQuery("");
    if (result) {
      // Log search history — fire and forget, non-blocking
      api.post("/api/search/history", {
        query,
        result_id: result.id,
        result_type: result.type,
        href,
      }).catch(() => {});
    }
  }

  // Group results by type
  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    (acc[r.type] ??= []).push(r);
    return acc;
  }, {});

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[18vh]">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />
      <div className="relative w-full max-w-xl mx-4">
        <Command
          className="overflow-hidden"
          style={{
            background: "var(--vf-bg-surface)",
            border: "1px solid var(--vf-border)",
            borderRadius: 18,
            boxShadow: "0 24px 80px rgba(0,0,0,0.4)",
          }}
        >
          {/* Input */}
          <div className="flex items-center gap-3 px-4"
            style={{ borderBottom: "1px solid var(--vf-divider)" }}>
            <Search className="h-4 w-4 vf-text-m shrink-0" />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Search or jump to…"
              className="flex h-12 w-full bg-transparent py-3 text-sm outline-none placeholder:vf-text-m vf-text-1"
            />
            <kbd className="hidden sm:inline-flex h-5 items-center gap-0.5 rounded px-1.5 text-[10px] font-medium vf-text-m"
              style={{ border: "1px solid var(--vf-border)", background: "var(--vf-bg-elevated)" }}>
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm vf-text-m">
              {searching ? "Searching…" : query.length >= 2 ? "No results found" : "Type to search"}
            </Command.Empty>

            {/* Quick nav when no query */}
            {!query && (
              <Command.Group
                heading={
                  <span className="px-2 text-[10px] font-semibold uppercase tracking-wider vf-text-m">
                    Navigate
                  </span>
                }
              >
                {NAV.map(({ label, href, icon: Icon }) => (
                  <Command.Item
                    key={href}
                    value={label}
                    onSelect={() => go(href)}
                    className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm vf-text-1"
                    style={{ outline: "none" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--vf-bg-elevated)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <Icon className="h-4 w-4 vf-text-m shrink-0" />
                    {label}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {/* Search results grouped by type */}
            {Object.entries(grouped).map(([type, items]) => (
              <Command.Group
                key={type}
                heading={
                  <span className="px-2 text-[10px] font-semibold uppercase tracking-wider vf-text-m capitalize">
                    {type}s
                  </span>
                }
              >
                {items.map(r => (
                  <Command.Item
                    key={r.id}
                    value={r.label}
                    onSelect={() => go(r.href, r)}
                    className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm vf-text-1"
                    style={{ outline: "none" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--vf-bg-elevated)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <span className={`inline-flex h-6 w-6 items-center justify-center rounded-lg text-[10px] font-bold uppercase ${
                      TYPE_BADGE[r.type] ?? "bg-gray-500/10 text-gray-400"
                    }`}>
                      {r.type[0]}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-medium vf-text-1">{r.label}</p>
                      <p className="truncate text-xs vf-text-m">{r.sub}</p>
                    </div>
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
