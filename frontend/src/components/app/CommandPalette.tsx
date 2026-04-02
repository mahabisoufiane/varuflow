"use client";

import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import {
  BarChart3, FileText, LayoutDashboard, Package,
  RefreshCw, Settings, ShoppingCart, Users,
} from "lucide-react";

interface SearchResult {
  id: string;
  label: string;
  sub: string;
  href: string;
  type: "invoice" | "customer" | "product";
}

const NAV = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Inventory", href: "/inventory", icon: Package },
  { label: "Invoices", href: "/invoices", icon: FileText },
  { label: "Recurring", href: "/recurring", icon: RefreshCw },
  { label: "Cash Register", href: "/pos", icon: ShoppingCart },
  { label: "Customers", href: "/customers", icon: Users },
  { label: "Settings", href: "/settings", icon: Settings },
];

export default function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!query.trim() || query.length < 2) { setResults([]); return; }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const [products, customers, invoices] = await Promise.allSettled([
          api.get<any[]>(`/api/inventory/products?q=${encodeURIComponent(query)}`),
          api.get<any[]>(`/api/invoicing/customers?q=${encodeURIComponent(query)}`),
          api.get<any[]>(`/api/invoicing/invoices?q=${encodeURIComponent(query)}`),
        ]);
        const out: SearchResult[] = [];
        if (products.status === "fulfilled") {
          products.value.slice(0, 3).forEach((p: any) => out.push({ id: p.id, label: p.name, sub: p.sku, href: `/inventory/products/${p.id}`, type: "product" }));
        }
        if (customers.status === "fulfilled") {
          customers.value.slice(0, 3).forEach((c: any) => out.push({ id: c.id, label: c.company_name, sub: c.email ?? "Customer", href: `/customers`, type: "customer" }));
        }
        if (invoices.status === "fulfilled") {
          invoices.value.slice(0, 3).forEach((i: any) => out.push({ id: i.id, label: i.invoice_number, sub: i.customer_name ?? "Invoice", href: `/invoices/${i.id}`, type: "invoice" }));
        }
        setResults(out);
      } finally { setSearching(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  function go(href: string) {
    router.push(href);
    setOpen(false);
    setQuery("");
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-xl mx-4">
        <Command className="rounded-2xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
          <div className="flex items-center border-b px-4 gap-3">
            <svg className="h-4 w-4 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Search or jump to…"
              className="flex h-12 w-full rounded-none bg-transparent py-3 text-sm outline-none placeholder:text-gray-400 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <kbd className="hidden sm:inline-flex h-5 items-center gap-1 rounded border border-gray-200 bg-gray-50 px-1.5 text-[10px] font-medium text-gray-500">
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-gray-500">
              {searching ? "Searching…" : "No results"}
            </Command.Empty>

            {!query && (
              <Command.Group heading={<span className="px-2 text-xs font-medium text-gray-400 uppercase tracking-wider">Navigate</span>}>
                {NAV.map(({ label, href, icon: Icon }) => (
                  <Command.Item
                    key={href}
                    value={label}
                    onSelect={() => go(href)}
                    className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 aria-selected:bg-gray-100"
                  >
                    <Icon className="h-4 w-4 text-gray-400 shrink-0" />
                    {label}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {results.length > 0 && (
              <Command.Group heading={<span className="px-2 text-xs font-medium text-gray-400 uppercase tracking-wider">Results</span>}>
                {results.map((r) => (
                  <Command.Item
                    key={r.id}
                    value={r.label}
                    onSelect={() => go(r.href)}
                    className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 aria-selected:bg-gray-100"
                  >
                    <span className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold uppercase ${
                      r.type === "product" ? "bg-blue-100 text-blue-700" :
                      r.type === "customer" ? "bg-purple-100 text-purple-700" :
                      "bg-green-100 text-green-700"
                    }`}>{r.type[0]}</span>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{r.label}</p>
                      <p className="truncate text-xs text-gray-400">{r.sub}</p>
                    </div>
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
