"use client";

import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import {
  ShoppingBag, Users, Bell, BookOpen, Building2, Plug,
  CheckCircle2, Circle, ExternalLink, Zap,
} from "lucide-react";

interface ConnectorCard {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: React.ReactNode;
  href: string;
  statusEndpoint?: string;
}

const CONNECTORS: ConnectorCard[] = [
  { id: "shopify", name: "Shopify", description: "Pull orders → invoices, push inventory levels", category: "E-commerce", icon: <ShoppingBag className="h-6 w-6" />, href: "integrations/shopify", statusEndpoint: "/api/integrations/shopify/status" },
  { id: "woocommerce", name: "WooCommerce", description: "Import WooCommerce orders and sync stock", category: "E-commerce", icon: <ShoppingBag className="h-6 w-6" />, href: "integrations/shopify", statusEndpoint: "/api/integrations/woocommerce/status" },
  { id: "hubspot", name: "HubSpot", description: "Sync customers and deals with your CRM", category: "CRM", icon: <Users className="h-6 w-6" />, href: "integrations/crm", statusEndpoint: "/api/integrations/hubspot/status" },
  { id: "salesforce", name: "Salesforce", description: "Push accounts and opportunities to Salesforce", category: "CRM", icon: <Users className="h-6 w-6" />, href: "integrations/crm", statusEndpoint: "/api/integrations/salesforce/status" },
  { id: "slack", name: "Slack", description: "Get notified on low stock, overdue invoices, new POs", category: "Notifications", icon: <Bell className="h-6 w-6" />, href: "integrations/notifications" },
  { id: "teams", name: "Microsoft Teams", description: "Push Varuflow events to your Teams channels", category: "Notifications", icon: <Bell className="h-6 w-6" />, href: "integrations/notifications" },
  { id: "visma", name: "Visma eEkonomi", description: "Push invoices and customers to Visma accounting", category: "Accounting", icon: <BookOpen className="h-6 w-6" />, href: "integrations/accounting", statusEndpoint: "/api/integrations/visma/status" },
  { id: "bokio", name: "Bokio", description: "Sync with Bokio bookkeeping (invite-only beta)", category: "Accounting", icon: <BookOpen className="h-6 w-6" />, href: "integrations/accounting", statusEndpoint: "/api/integrations/bokio/status" },
  { id: "nordigen", name: "Open Banking (GoCardless)", description: "Import bank transactions from 2 000+ European banks", category: "Banking", icon: <Building2 className="h-6 w-6" />, href: "integrations/banking" },
  { id: "zapier", name: "Zapier", description: "Connect Varuflow to 6 000+ apps with no code", category: "Automation", icon: <Zap className="h-6 w-6" />, href: "integrations/zapier" },
  { id: "make", name: "Make (formerly Integromat)", description: "Build visual automation workflows with Varuflow triggers", category: "Automation", icon: <Zap className="h-6 w-6" />, href: "integrations/zapier" },
];

const CATEGORIES = ["E-commerce", "CRM", "Notifications", "Accounting", "Banking", "Automation"];

export default function IntegrationsPage() {
  const locale = useLocale();
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [statuses, setStatuses] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function fetchStatuses() {
      const endpoints = CONNECTORS.filter(c => c.statusEndpoint);
      const results = await Promise.allSettled(
        endpoints.map(async (c) => {
          const res = await fetch(`${apiBase}${c.statusEndpoint!}`, { credentials: "include" });
          if (!res.ok) return { id: c.id, connected: false };
          const data = await res.json();
          return { id: c.id, connected: data.connected ?? data.is_active ?? false };
        })
      );
      const map: Record<string, boolean> = {};
      for (const r of results) {
        if (r.status === "fulfilled") {
          map[r.value.id] = r.value.connected;
        }
      }
      setStatuses(map);
    }
    fetchStatuses();
  }, [apiBase]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Integrations Marketplace</h1>
        <p className="mt-1 text-sm text-gray-500">
          Connect Varuflow to your existing tools — e-commerce, CRM, accounting, banking, and automation.
        </p>
      </div>

      {CATEGORIES.map((category) => {
        const connectors = CONNECTORS.filter(c => c.category === category);
        return (
          <div key={category}>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">{category}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {connectors.map((c) => {
                const connected = statuses[c.id];
                return (
                  <a
                    key={c.id}
                    href={`/${locale}/${c.href}`}
                    className="group flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-sm hover:border-blue-400 hover:shadow-md transition-all"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-gray-600 group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors">
                          {c.icon}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 text-sm">{c.name}</p>
                          <p className="text-xs text-gray-400">{c.category}</p>
                        </div>
                      </div>
                      {c.statusEndpoint ? (
                        connected ? (
                          <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                            <CheckCircle2 className="h-3.5 w-3.5" /> Connected
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-gray-400">
                            <Circle className="h-3.5 w-3.5" /> Not connected
                          </span>
                        )
                      ) : null}
                    </div>
                    <p className="text-xs text-gray-500">{c.description}</p>
                    <span className="flex items-center gap-1 text-xs text-blue-600 font-medium mt-auto">
                      Configure <ExternalLink className="h-3 w-3" />
                    </span>
                  </a>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
