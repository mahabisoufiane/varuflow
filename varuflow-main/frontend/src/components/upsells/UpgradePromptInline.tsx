"use client";
/**
 * UpgradePromptInline — small inline upgrade nudge for placement="inline".
 * Typically rendered inside a feature section or settings panel below
 * feature description text. Non-intrusive; dismissible with an X.
 */
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sparkles, X } from "lucide-react";
import type { UpsellTrigger } from "@/hooks/useUpsells";

interface UpgradePromptInlineProps {
  trigger: UpsellTrigger;
  onShown: (t: UpsellTrigger) => void;
  onClicked: (t: UpsellTrigger) => void;
  onDismissed: (t: UpsellTrigger) => void;
}

export default function UpgradePromptInline({
  trigger,
  onShown,
  onClicked,
  onDismissed,
}: UpgradePromptInlineProps) {
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) ?? "en";
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    onShown(trigger);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger.id]);

  if (!visible) return null;

  function handleUpgrade() {
    void onClicked(trigger);
    router.push(`/${locale}/settings/billing`);
  }

  function handleDismiss() {
    setVisible(false);
    void onDismissed(trigger);
  }

  return (
    <div className="flex items-start gap-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-800">
      <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
      <div className="flex-1">
        <p className="leading-snug">{trigger.message}</p>
        <Button
          variant="link"
          size="sm"
          className="mt-1 h-auto p-0 text-indigo-700 font-medium"
          onClick={handleUpgrade}
        >
          {trigger.cta} →
        </Button>
      </div>
      <button
        aria-label="Dismiss"
        className="rounded p-0.5 text-indigo-400 hover:text-indigo-700"
        onClick={handleDismiss}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
