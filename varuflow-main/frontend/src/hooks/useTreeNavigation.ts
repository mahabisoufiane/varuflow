// File: src/hooks/useTreeNavigation.ts
// Purpose: State + interaction logic for <ResourceTree /> — expand/collapse,
// search-as-you-type filtering, and keyboard navigation (up/down/enter, plus
// left/right to collapse/expand). Kept out of the view so the component stays
// presentational. Label resolution is injected (resolveLabel) so filtering
// matches the *translated* label, not the i18n key.

import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import type { TreeNode } from "@/components/console/resource-tree.config";

export interface FlatNode {
  node: TreeNode;
  depth: number;
  hasChildren: boolean;
  expanded: boolean;
}

interface Params {
  tree: TreeNode[];
  /** id of the node matching the current route (drives active + auto-expand). */
  activeId: string | null;
  /** Resolve a node's display label (used for case-insensitive filtering). */
  resolveLabel: (node: TreeNode) => string;
  /** Called on Enter / click-through — navigate for leaves, toggle for groups. */
  onActivate: (node: TreeNode) => void;
}

/** Ancestor ids of `id` (excluding the node itself), or [] if not found. */
function findAncestors(nodes: TreeNode[], id: string, trail: string[] = []): string[] | null {
  for (const node of nodes) {
    if (node.id === id) return trail;
    if (node.children) {
      const res = findAncestors(node.children, id, [...trail, node.id]);
      if (res) return res;
    }
  }
  return null;
}

export function useTreeNavigation({ tree, activeId, resolveLabel, onActivate }: Params) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [focusedId, setFocusedId] = useState<string | null>(activeId);

  // Auto-expand the ancestors of the active route so the current page is always
  // revealed, and sync keyboard focus to it.
  useEffect(() => {
    if (!activeId) return;
    const ancestors = findAncestors(tree, activeId) ?? [];
    if (ancestors.length) {
      setExpanded((prev) => {
        const next = new Set(prev);
        ancestors.forEach((id) => next.add(id));
        return next;
      });
    }
    setFocusedId(activeId);
  }, [activeId, tree]);

  const q = query.trim().toLowerCase();

  // When filtering, keep any node that matches or has a matching descendant.
  const filterKeep = useMemo(() => {
    if (!q) return null;
    const keep = new Set<string>();
    const walk = (node: TreeNode): boolean => {
      const selfMatch = resolveLabel(node).toLowerCase().includes(q);
      let childMatch = false;
      node.children?.forEach((c) => {
        if (walk(c)) childMatch = true;
      });
      if (selfMatch || childMatch) keep.add(node.id);
      return selfMatch || childMatch;
    };
    tree.forEach(walk);
    return keep;
  }, [q, tree, resolveLabel]);

  const isExpanded = useCallback(
    (id: string) => (filterKeep ? true : expanded.has(id)), // filtering auto-expands
    [filterKeep, expanded]
  );

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  // Flatten to the currently-visible rows (respecting filter + expand state).
  const visible = useMemo<FlatNode[]>(() => {
    const out: FlatNode[] = [];
    const walk = (nodes: TreeNode[], depth: number) => {
      for (const node of nodes) {
        if (filterKeep && !filterKeep.has(node.id)) continue;
        const hasChildren = !!node.children?.length;
        const exp = hasChildren && isExpanded(node.id);
        out.push({ node, depth, hasChildren, expanded: exp });
        if (exp) walk(node.children!, depth + 1);
      }
    };
    walk(tree, 0);
    return out;
  }, [tree, filterKeep, isExpanded]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible.length) return;
      const idx = Math.max(0, visible.findIndex((v) => v.node.id === focusedId));
      const cur = visible[idx];
      const focusAt = (delta: number) => {
        e.preventDefault();
        const next = visible[(idx + delta + visible.length) % visible.length];
        setFocusedId(next.node.id);
      };
      switch (e.key) {
        case "ArrowDown": focusAt(1); break;
        case "ArrowUp": focusAt(-1); break;
        case "Enter":
          if (cur) {
            e.preventDefault();
            // Pure grouping node (no route) → toggle; everything else activates.
            if (cur.hasChildren && !cur.node.href) toggle(cur.node.id);
            else onActivate(cur.node);
          }
          break;
        case "ArrowRight":
          if (cur?.hasChildren && !cur.expanded) { e.preventDefault(); toggle(cur.node.id); }
          break;
        case "ArrowLeft":
          if (cur?.hasChildren && cur.expanded) { e.preventDefault(); toggle(cur.node.id); }
          break;
      }
    },
    [visible, focusedId, onActivate, toggle]
  );

  return { query, setQuery, isExpanded, toggle, visible, focusedId, setFocusedId, onKeyDown };
}
