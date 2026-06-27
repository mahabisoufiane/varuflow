"use client";

/**
 * RoleProvider / useRole / RoleGuard — the frontend half of role-within-module
 * access control. Mirrors the backend `require_role` gate.
 *
 * RoleProvider fetches `/api/auth/me` once and exposes the caller's role and
 * module grants to the whole app shell. Pages use:
 *   • `useRole()`           to branch UI on role
 *   • `<RoleGuard minRole>` to block an entire page from a too-junior member
 *     (this protects against direct-URL access — hiding a nav link is not a
 *     security boundary on its own).
 */
import { createContext, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api-client";
import { hasMinRole, type OrgRole } from "@/lib/roles";

interface MePayload {
  role?: string;
  allowed_modules?: string[];
  plan_modules?: string[];
  plan?: string;
  organization?: { plan?: string };
}

interface RoleContextValue {
  role: OrgRole | null;
  allowedModules: string[];
  planModules: string[];
  plan: string | null;
  loading: boolean;
}

const RoleContext = createContext<RoleContextValue>({
  role: null,
  allowedModules: ["*"],
  planModules: ["*"],
  plan: null,
  loading: true,
});

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState<RoleContextValue>({
    role: null,
    allowedModules: ["*"],
    planModules: ["*"],
    plan: null,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;
    api
      .get<MePayload>("/api/auth/me", { silent: true })
      .then((me) => {
        if (cancelled) return;
        setValue({
          role: (me.role as OrgRole) ?? null,
          allowedModules: me.allowed_modules ?? ["*"],
          planModules: me.plan_modules ?? ["*"],
          plan: me.plan ?? me.organization?.plan ?? null,
          loading: false,
        });
      })
      .catch(() => {
        if (!cancelled) setValue((v) => ({ ...v, loading: false }));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  return useContext(RoleContext);
}

/**
 * Gate a page (or section) behind a minimum role. While `/api/auth/me` is in
 * flight we render nothing to avoid a flash of forbidden content. Once loaded,
 * an insufficient role gets a clear "not authorised" panel instead of the page.
 */
export function RoleGuard({
  minRole,
  children,
  fallback,
}: {
  minRole: OrgRole;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { role, loading } = useRole();

  if (loading) return null;

  if (!hasMinRole(role, minRole)) {
    if (fallback !== undefined) return <>{fallback}</>;
    return (
      <div className="vf-section p-8 text-center space-y-2">
        <h2 className="text-lg font-semibold vf-text">Not authorised</h2>
        <p className="text-sm vf-text-m">
          This page requires the <strong>{minRole}</strong> role. Ask your
          organisation owner if you need access.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
