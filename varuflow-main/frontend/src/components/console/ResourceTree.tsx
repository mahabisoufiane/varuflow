// File: src/components/console/ResourceTree.tsx
// Purpose: Region 2 of the operator console — a persistent, collapsible,
// config-driven hierarchical navigation tree (domain > entity > sub-entity).
// It ONLY navigates (next-intl router, locale-preserved); active selection is
// derived from the current route, so all existing routing/guards are intact.
//
// Reuse: permission model (useRole + hasMinRole + module grants) is identical to
// the legacy AppShell sidebar. Interaction/keyboard state lives in
// useTreeNavigation. Styling is Tailwind + shadcn theme tokens (no CSS module).

"use client";

import { useCallback, useMemo } from "react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { ChevronRight, Search, X } from "lucide-react";

import { useRole } from "@/components/app/RoleContext";
import { hasMinRole } from "@/lib/roles";
import { cn } from "@/lib/utils";
import { CONSOLE_TREE, type TreeNode } from "@/components/console/resource-tree.config";
import { useTreeNavigation } from "@/hooks/useTreeNavigation";

/** Recursively drop nodes the current member may not see (module + role gates),
 *  mirroring the backend require_module/require_role guards. */
function filterByPermissions(
  nodes: TreeNode[],
  allowedModules: string[],
  role: Parameters<typeof hasMinRole>[0]
): TreeNode[] {
  const wildcard = allowedModules.includes("*");
  const canSee = (n: TreeNode) =>
    (wildcard || !n.module || allowedModules.includes(n.module)) &&
    (!n.minRole || hasMinRole(role, n.minRole));
  return nodes
    .filter(canSee)
    .map((n) =>
      n.children ? { ...n, children: filterByPermissions(n.children, allowedModules, role) } : n
    );
}

/** id of the tree node whose href best (longest) matches the current path. */
function computeActiveId(nodes: TreeNode[], pathname: string): string | null {
  let bestId: string | null = null;
  let bestLen = -1;
  const walk = (list: TreeNode[]) => {
    for (const n of list) {
      if (n.href && (pathname === n.href || pathname.startsWith(n.href + "/")) && n.href.length > bestLen) {
        bestId = n.id;
        bestLen = n.href.length;
      }
      if (n.children) walk(n.children);
    }
  };
  walk(nodes);
  return bestId;
}

export default function ResourceTree({
  onNavigate,
  className,
}: {
  /** Called after a navigation (e.g. to close the mobile slide-over). */
  onNavigate?: () => void;
  className?: string;
}) {
  const t = useTranslations("console");
  const pathname = usePathname(); // next-intl → already locale-stripped
  const router = useRouter();
  const { role, allowedModules } = useRole();

  const tree = useMemo(
    () => filterByPermissions(CONSOLE_TREE, allowedModules, role),
    [allowedModules, role]
  );
  const activeId = useMemo(() => computeActiveId(tree, pathname), [tree, pathname]);

  const resolveLabel = useCallback(
    (node: TreeNode) => t(node.labelKey as Parameters<typeof t>[0]),
    [t]
  );

  const onActivate = useCallback(
    (node: TreeNode) => {
      if (node.href) {
        router.push(node.href);
        onNavigate?.();
      }
    },
    [router, onNavigate]
  );

  const { query, setQuery, isExpanded, toggle, visible, focusedId, setFocusedId, onKeyDown } =
    useTreeNavigation({ tree, activeId, resolveLabel, onActivate });

  return (
    <div className={cn("flex h-full flex-col bg-background", className)}>
      {/* Search-as-you-type */}
      <div className="relative p-2">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("tree.searchPlaceholder")}
          aria-label={t("tree.searchPlaceholder")}
          className="h-8 w-full rounded-md border bg-background pl-8 pr-7 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear"
            className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Tree */}
      <div
        role="tree"
        tabIndex={0}
        onKeyDown={onKeyDown}
        aria-label="Resource tree"
        className="flex-1 overflow-y-auto px-1 pb-2 outline-none focus:ring-1 focus:ring-inset focus:ring-ring"
      >
        {visible.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">{t("tree.noResults")}</p>
        ) : (
          visible.map(({ node, depth, hasChildren, expanded }) => {
            const Icon = node.icon;
            const active = node.id === activeId;
            const focused = node.id === focusedId;
            return (
              <div
                key={node.id}
                role="treeitem"
                aria-selected={active}
                aria-expanded={hasChildren ? expanded : undefined}
                onMouseEnter={() => setFocusedId(node.id)}
                onClick={() => (node.href ? onActivate(node) : hasChildren && toggle(node.id))}
                style={{ paddingLeft: 8 + depth * 14 }}
                className={cn(
                  "flex cursor-pointer select-none items-center gap-1.5 rounded-md py-1.5 pr-2 text-sm",
                  active
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  focused && "ring-1 ring-inset ring-ring"
                )}
              >
                {hasChildren ? (
                  <button
                    type="button"
                    aria-label={expanded ? "Collapse" : "Expand"}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggle(node.id);
                    }}
                    className="grid h-4 w-4 shrink-0 place-items-center rounded hover:bg-accent"
                  >
                    <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-90")} />
                  </button>
                ) : (
                  <span className="h-4 w-4 shrink-0" />
                )}
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{resolveLabel(node)}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
