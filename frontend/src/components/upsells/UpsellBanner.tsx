"use client";
/**
 * UpsellBanner — inline alert bar for upsell triggers with placement="banner".
 * Renders below the page header, above the main content area.
 */
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { X, ArrowRight } from "lucide-react";
import type { UpsellTrigger } from "@/hooks/useUpsells";

interface UpsellBannerProps {
  trigger: UpsellTrigger;
  onShown: (t: UpsellTrigger) => void;
  onClicked: (t: UpsellTrigger) => void;
  onDismissed: (t: UpsellTrigger) => void;
}

export default function UpsellBanner({
  trigger,
  onShown,
  onClicked,
  onDismissed,
}: UpsellBannerProps) {
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
    <div
      role="alert"
      className="flex items-center justify-between gap-3 rounded-md border border-yellow-300 bg-yellow-50 px-4 py-2.5 text-sm text-yellow-800"
    >
      <span className="flex-1 leading-snug">{trigger.message}</span>
      <div className="flex items-center gap-2 shrink-0">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-yellow-700 hover:text-yellow-900 hover:bg-yellow-100 px-2"
          onClick={handleUpgrade}
        >
          {trigger.cta}
          <ArrowRight className="ml-1 h-3.5 w-3.5" />
        </Button>
        <button
          aria-label="Dismiss"
          className="rounded p-0.5 text-yellow-600 hover:text-yellow-900"
          onClick={handleDismiss}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
