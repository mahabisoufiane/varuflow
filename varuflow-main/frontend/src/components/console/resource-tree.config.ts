// File: src/components/console/resource-tree.config.ts
// Purpose: Config-driven data for the operator-console <ResourceTree />.
// Domain > entity > sub-entity, each wired to a REAL existing route so all
// current App Router pages, i18n prefixes and permission redirects keep working
// (the tree only navigates — it does not own any business logic).
//
// Gating reuses the same model as the legacy AppShell sidebar:
//   - `module`  → shown when useRole().allowedModules includes it (or "*")
//   - `minRole` → shown when hasMinRole(role, minRole) (role-within-module)
// Keep these in sync with the backend require_role()/require_module guards.
//
// Labels are i18n keys under the `console.tree.*` namespace (added to
// messages/*.json) so the tree is self-contained and never throws on a missing
// legacy `nav.*` key. Adding a domain = adding a node here; no component change.

import {
  LayoutDashboard, Users, FileSignature, ShoppingBag, FileText, Package,
  Warehouse, ClipboardList, Truck, CreditCard, TrendingUp, BarChart3, Zap,
  ShieldCheck, Settings, type LucideIcon,
} from "lucide-react";
import type { OrgRole } from "@/lib/roles";

export interface TreeNode {
  /** Stable id (used for expand state, keyboard focus, active matching). */
  id: string;
  /** i18n key under the `console.tree.*` namespace. */
  labelKey: string;
  icon: LucideIcon;
  /** Locale-agnostic route; next-intl <Link> adds the locale prefix. Omit for
   *  pure grouping nodes that only expand/collapse. */
  href?: string;
  /** Module gate — matches useRole().allowedModules (or "*"). */
  module?: string;
  /** Role-within-module gate — matches hasMinRole(role, minRole). */
  minRole?: OrgRole;
  children?: TreeNode[];
}

// The 15 domains from the brief, in order. Some map to a sub-route because no
// dedicated top-level route exists yet — those are marked [MAP] and are a
// one-line change if you add the dedicated route later.
export const CONSOLE_TREE: TreeNode[] = [
  {
    id: "dashboard",
    labelKey: "tree.dashboard",
    icon: LayoutDashboard,
    href: "/dashboard",
    module: "dashboard",
  },
  {
    id: "customers",
    labelKey: "tree.customers",
    icon: Users,
    href: "/customers",
    module: "invoicing",
    children: [
      { id: "customers.all", labelKey: "tree.customersAll", icon: Users, href: "/customers", module: "invoicing" },
      { id: "customers.leads", labelKey: "tree.leads", icon: Users, href: "/crm/leads", module: "crm" },
      { id: "customers.b2b", labelKey: "tree.b2bHub", icon: ShoppingBag, href: "/b2b", module: "crm" },
    ],
  },
  {
    id: "quotes",
    labelKey: "tree.quotes",
    icon: FileSignature,
    href: "/quotes",
    module: "invoicing",
  },
  {
    id: "orders",
    labelKey: "tree.orders",
    icon: ShoppingBag,
    href: "/shop/orders", // [MAP] no dedicated /orders route; alt: /b2b
    module: "invoicing",
    children: [
      { id: "orders.b2b", labelKey: "tree.b2bOrders", icon: ShoppingBag, href: "/b2b/buyer-pos", module: "crm" },
      { id: "orders.shop", labelKey: "tree.shopOrders", icon: ShoppingBag, href: "/shop/orders", module: "invoicing" },
      { id: "orders.pos", labelKey: "tree.pos", icon: CreditCard, href: "/pos", module: "pos" },
    ],
  },
  {
    id: "invoices",
    labelKey: "tree.invoices",
    icon: FileText,
    href: "/invoices",
    module: "invoicing",
    children: [
      { id: "invoices.all", labelKey: "tree.invoicesAll", icon: FileText, href: "/invoices", module: "invoicing" },
      { id: "invoices.recurring", labelKey: "tree.recurring", icon: FileText, href: "/recurring", module: "invoicing" },
      { id: "invoices.recon", labelKey: "tree.reconciliation", icon: BarChart3, href: "/reconciliation", module: "finance", minRole: "ADMIN" },
    ],
  },
  {
    id: "inventory",
    labelKey: "tree.inventory",
    icon: Package,
    href: "/inventory",
    module: "inventory",
    children: [
      { id: "inventory.products", labelKey: "tree.products", icon: Package, href: "/inventory/products", module: "inventory" },
      { id: "inventory.kitting", labelKey: "tree.kitting", icon: Package, href: "/kitting", module: "inventory" },
      { id: "inventory.landed", labelKey: "tree.landedCosts", icon: TrendingUp, href: "/landed-costs", module: "inventory" },
    ],
  },
  {
    id: "warehouses",
    labelKey: "tree.warehouses",
    icon: Warehouse,
    href: "/inventory/warehouses",
    module: "inventory",
  },
  {
    id: "purchaseOrders",
    labelKey: "tree.purchaseOrders",
    icon: ClipboardList,
    href: "/inventory/purchase-orders",
    module: "inventory",
    children: [
      { id: "po.requests", labelKey: "tree.purchaseRequests", icon: ClipboardList, href: "/purchase-requests", module: "finance" },
    ],
  },
  {
    id: "suppliers",
    labelKey: "tree.suppliers",
    icon: Truck,
    href: "/inventory/suppliers",
    module: "inventory",
  },
  {
    id: "payments",
    labelKey: "tree.payments",
    icon: CreditCard,
    href: "/payment-options", // [MAP] alt: /local-payments
    module: "invoicing",
    children: [
      { id: "payments.options", labelKey: "tree.paymentOptions", icon: CreditCard, href: "/payment-options", module: "invoicing" },
      { id: "payments.local", labelKey: "tree.localPayments", icon: CreditCard, href: "/local-payments", module: "invoicing" },
      { id: "payments.deposits", labelKey: "tree.deposits", icon: CreditCard, href: "/deposits", module: "invoicing" },
    ],
  },
  {
    id: "cashflow",
    labelKey: "tree.cashFlow",
    icon: TrendingUp,
    href: "/ceo/cash-forecast", // [MAP] alt: /cashflow-prediction
    module: "finance",
    minRole: "ADMIN",
    children: [
      { id: "cashflow.forecast", labelKey: "tree.cashForecast", icon: TrendingUp, href: "/ceo/cash-forecast", module: "finance", minRole: "ADMIN" },
      { id: "cashflow.prediction", labelKey: "tree.cashPrediction", icon: TrendingUp, href: "/cashflow-prediction", module: "finance", minRole: "ADMIN" },
    ],
  },
  {
    id: "analytics",
    labelKey: "tree.analytics",
    icon: BarChart3,
    href: "/analytics",
    module: "analytics",
    children: [
      { id: "analytics.overview", labelKey: "tree.analyticsOverview", icon: BarChart3, href: "/analytics", module: "analytics" },
      { id: "analytics.dashboards", labelKey: "tree.biDashboards", icon: LayoutDashboard, href: "/analytics/dashboard", module: "analytics" },
      { id: "analytics.reports", labelKey: "tree.biReports", icon: ClipboardList, href: "/analytics/reports", module: "analytics" },
      { id: "analytics.pnl", labelKey: "tree.pnl", icon: BarChart3, href: "/reports/pnl", module: "analytics" },
    ],
  },
  {
    id: "automation",
    labelKey: "tree.automation",
    icon: Zap,
    href: "/ai/automation",
    module: "ai",
    children: [
      { id: "automation.runs", labelKey: "tree.automationRuns", icon: Zap, href: "/ai/automation", module: "ai" },
      { id: "automation.workflows", labelKey: "tree.workflows", icon: Zap, href: "/ai/workflows", module: "ai" },
      { id: "automation.advisor", labelKey: "tree.aiAdvisor", icon: Zap, href: "/ai", module: "ai" },
    ],
  },
  {
    id: "compliance",
    labelKey: "tree.compliance",
    icon: ShieldCheck,
    href: "/compliance",
    module: "settings",
    children: [
      { id: "compliance.overview", labelKey: "tree.complianceOverview", icon: ShieldCheck, href: "/compliance", module: "settings" },
      { id: "compliance.governance", labelKey: "tree.governance", icon: ShieldCheck, href: "/governance", module: "settings", minRole: "ADMIN" },
      { id: "compliance.gdpr", labelKey: "tree.gdpr", icon: ShieldCheck, href: "/gdpr", module: "settings", minRole: "ADMIN" },
    ],
  },
  {
    id: "settings",
    labelKey: "tree.settings",
    icon: Settings,
    href: "/settings",
    module: "settings",
    children: [
      { id: "settings.general", labelKey: "tree.settingsGeneral", icon: Settings, href: "/settings", module: "settings" },
      { id: "settings.integrations", labelKey: "tree.integrations", icon: Settings, href: "/integrations", module: "settings" },
      { id: "settings.multiEntity", labelKey: "tree.multiEntity", icon: Settings, href: "/multi-entity", module: "settings" },
    ],
  },
];
