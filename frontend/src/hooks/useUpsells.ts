"use client";
/**
 * useUpsells — polls /api/upsells/pending, applies client-side frequency caps,
 * and exposes helpers to record shown/clicked/dismissed events.
 *
 * Anti-annoyance enforced here (in addition to server-side rules):
 * - Max 1 modal per session (tracked via sessionStorage)
 * - Max 1 banner per page mount
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { track } from "@/lib/analytics";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function getToken(): string {
  return typeof window !== "undefined"
    ? (localStorage.getItem("auth_token") ?? "")
    : "";
}

export interface UpsellTrigger {
  id: string;
  name: string;
  message: string;
  cta: string;
  target_tier: string;
  placement: "modal" | "banner" | "toast" | "inline";
  priority: number;
}

interface UseUpsellsOptions {
  /** If the user just attempted to use a locked feature, pass its name here. */
  lockedFeature?: string;
  /** Whether to auto-poll on mount (default: true) */
  autoFetch?: boolean;
}

const SESSION_MODAL_SHOWN_KEY = "varuflow_upsell_modal_shown";

export function useUpsells(options: UseUpsellsOptions = {}) {
  const { lockedFeature, autoFetch = true } = options;

  const [triggers, setTriggers] = useState<UpsellTrigger[]>([]);
  const [loading, setLoading] = useState(false);
  const bannerShownThisMount = useRef(false);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const query = lockedFeature
        ? `?locked_feature=${encodeURIComponent(lockedFeature)}`
        : "";
      const res = await fetch(`${API}/api/upsells/pending${query}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) return;
      const raw: UpsellTrigger[] = await res.json();

      // Client-side frequency cap: only 1 modal per session
      const modalAlreadyShown =
        typeof window !== "undefined" &&
        !!sessionStorage.getItem(SESSION_MODAL_SHOWN_KEY);

      // Only 1 banner per page mount
      let bannerIncluded = bannerShownThisMount.current;

      const filtered = raw.filter((t) => {
        if (t.placement === "modal") {
          if (modalAlreadyShown) return false;
        }
        if (t.placement === "banner") {
          if (bannerIncluded) return false;
          bannerIncluded = true;
        }
        return true;
      });

      setTriggers(filtered);
    } catch {
      // Never block the app
    } finally {
      setLoading(false);
    }
  }, [lockedFeature]);

  useEffect(() => {
    if (autoFetch) {
      void fetchPending();
    }
  }, [autoFetch, fetchPending]);

  const recordShown = useCallback(
    async (trigger: UpsellTrigger) => {
      if (trigger.placement === "modal") {
        sessionStorage.setItem(SESSION_MODAL_SHOWN_KEY, "1");
      }
      if (trigger.placement === "banner") {
        bannerShownThisMount.current = true;
      }
      try {
        track("upsell_shown", {
          trigger_id: trigger.id,
          placement: trigger.placement,
          target_tier: trigger.target_tier,
        });
        await fetch(`${API}/api/upsells/shown`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${getToken()}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            trigger_id: trigger.id,
            placement: trigger.placement,
            target_tier: trigger.target_tier,
          }),
        });
      } catch {
        // Fire-and-forget
      }
    },
    [],
  );

  const recordClicked = useCallback(async (trigger: UpsellTrigger) => {
    try {
      track("upsell_clicked", {
        trigger_id: trigger.id,
        placement: trigger.placement,
        target_tier: trigger.target_tier,
      });
      await fetch(`${API}/api/upsells/clicked`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          trigger_id: trigger.id,
          placement: trigger.placement,
          target_tier: trigger.target_tier,
        }),
      });
    } catch {
      // Fire-and-forget
    }
  }, []);

  const recordDismissed = useCallback(
    async (trigger: UpsellTrigger) => {
      try {
        track("upsell_dismissed", {
          trigger_id: trigger.id,
          placement: trigger.placement,
        });
        await fetch(`${API}/api/upsells/dismissed`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${getToken()}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            trigger_id: trigger.id,
            placement: trigger.placement,
            target_tier: trigger.target_tier,
          }),
        });
        // Remove from local state so it disappears immediately
        setTriggers((prev) => prev.filter((t) => t.id !== trigger.id));
      } catch {
        // Fire-and-forget
      }
    },
    [],
  );

  const modal = triggers.find((t) => t.placement === "modal") ?? null;
  const banner = triggers.find((t) => t.placement === "banner") ?? null;
  const toasts = triggers.filter((t) => t.placement === "toast");
  const inlines = triggers.filter((t) => t.placement === "inline");

  return {
    triggers,
    loading,
    modal,
    banner,
    toasts,
    inlines,
    refresh: fetchPending,
    recordShown,
    recordClicked,
    recordDismissed,
  };
}
