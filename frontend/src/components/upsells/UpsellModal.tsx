"use client";
/**
 * UpsellModal — full-screen dialog shown for high-priority upsell triggers
 * (placement = "modal"). At most one per session (enforced in useUpsells).
 */
import { useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Zap } from "lucide-react";
import type { UpsellTrigger } from "@/hooks/useUpsells";
import { track } from "@/lib/analytics";

interface UpsellModalProps {
  trigger: UpsellTrigger;
  onShown: (t: UpsellTrigger) => void;
  onClicked: (t: UpsellTrigger) => void;
  onDismissed: (t: UpsellTrigger) => void;
}

export default function UpsellModal({
  trigger,
  onShown,
  onClicked,
  onDismissed,
}: UpsellModalProps) {
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) ?? "en";

  useEffect(() => {
    onShown(trigger);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger.id]);

  function handleUpgrade() {
    void onClicked(trigger);
    track("upsell_converted", {
      trigger_id: trigger.id,
      target_tier: trigger.target_tier,
      placement: "modal",
    });
    router.push(`/${locale}/settings/billing`);
  }

  function handleDismiss() {
    void onDismissed(trigger);
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) handleDismiss(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-5 w-5 text-yellow-500" />
            <span className="text-xs font-semibold uppercase tracking-wide text-yellow-600">
              Upgrade to {trigger.target_tier}
            </span>
          </div>
          <DialogTitle className="text-lg leading-snug">{trigger.name}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground mt-1">
            {trigger.message}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex gap-2 mt-4">
          <Button variant="outline" size="sm" onClick={handleDismiss}>
            Maybe later
          </Button>
          <Button size="sm" onClick={handleUpgrade}>
            {trigger.cta}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
