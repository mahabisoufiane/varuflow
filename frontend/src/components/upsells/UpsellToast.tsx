"use client";
/**
 * UpsellToast — celebratory / milestone upsell shown via toast notification.
 * Uses the same shadcn/ui Sonner toast pattern used elsewhere in the app.
 * Caller is expected to call toast() on mount; this component is a thin
 * wrapper that fires on first render and records the impression.
 */
import { useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import type { UpsellTrigger } from "@/hooks/useUpsells";

interface UpsellToastProps {
  trigger: UpsellTrigger;
  onShown: (t: UpsellTrigger) => void;
  onClicked: (t: UpsellTrigger) => void;
  onDismissed: (t: UpsellTrigger) => void;
}

export default function UpsellToast({
  trigger,
  onShown,
  onClicked,
  onDismissed,
}: UpsellToastProps) {
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) ?? "en";

  useEffect(() => {
    onShown(trigger);
    toast(trigger.message, {
      duration: 8000,
      action: {
        label: trigger.cta,
        onClick: () => {
          void onClicked(trigger);
          router.push(`/${locale}/settings/billing`);
        },
      },
      onDismiss: () => {
        void onDismissed(trigger);
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger.id]);

  // Renders nothing — side-effect only
  return null;
}
