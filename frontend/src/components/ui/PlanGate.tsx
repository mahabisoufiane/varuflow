"use client";

import { useState } from "react";
import { LockedFeatureCard } from "@/components/ui/LockedFeatureCard";

type ApiError = Error & { code?: string; module?: string; currentPlan?: string };

const MODULE_PLAN_MAP: Record<string, "PRO" | "ENTERPRISE"> = {
  analytics: "PRO",
  pos: "PRO",
  crm: "PRO",
  hr: "PRO",
  finance: "PRO",
  ai: "PRO",
  manufacturing: "PRO",
  compliance: "ENTERPRISE",
  multi_entity: "ENTERPRISE",
};

export function isPlanGateError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const e = err as ApiError;
  return e.code === "MODULE_NOT_IN_PLAN" || e.code === "FEATURE_NOT_AVAILABLE";
}

export function usePlanGate() {
  const [gateInfo, setGateInfo] = useState<{ module: string; plan: string } | null>(null);

  function checkError(err: unknown): boolean {
    if (!isPlanGateError(err)) return false;
    const e = err as ApiError;
    setGateInfo({ module: e.module ?? "unknown", plan: e.currentPlan ?? "FREE" });
    return true;
  }

  function reset() {
    setGateInfo(null);
  }

  return { gateInfo, checkError, reset };
}

interface PlanGateBlockProps {
  module: string;
  currentPlan: string;
  featureName: string;
  description?: string;
}

export function PlanGateBlock({ module, currentPlan, featureName, description }: PlanGateBlockProps) {
  const requiredPlan = MODULE_PLAN_MAP[module] ?? "PRO";
  return (
    <div className="p-6 max-w-lg mx-auto mt-12">
      <LockedFeatureCard
        featureName={featureName}
        requiredPlan={requiredPlan}
        description={description ?? `Upgrade to ${requiredPlan} to unlock ${featureName}. You're currently on the ${currentPlan} plan.`}
      />
    </div>
  );
}
