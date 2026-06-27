"use client";

// File: src/components/ui/LimitBlockedModal.tsx
// Purpose: Red modal shown when an action is blocked because the org has hit its plan limit.
// Used by: any create-action handler that receives a 403 PLAN_LIMIT_EXCEEDED response.

import { useRouter } from "next/navigation";
import { XCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface LimitBlockedModalProps {
  open: boolean;
  onClose: () => void;
  resource: string;
  current: number;
  limit: number;
  currentPlan: string;
  upgradeUrl?: string;
}

export function LimitBlockedModal({
  open,
  onClose,
  resource,
  current,
  limit,
  currentPlan,
  upgradeUrl = "/en/settings/billing",
}: LimitBlockedModalProps) {
  const router = useRouter();
  const label = resource.replace(/_/g, " ");

  function handleUpgrade() {
    onClose();
    router.push(upgradeUrl);
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <XCircle className="h-5 w-5 shrink-0" />
            <DialogTitle className="text-red-600 dark:text-red-400">
              Plan limit reached
            </DialogTitle>
          </div>
          <DialogDescription className="pt-2">
            Your <strong>{currentPlan}</strong> plan allows up to{" "}
            <strong>{limit}</strong> {label}. You currently have{" "}
            <strong>{current}</strong>. Upgrade your plan to add more.
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleUpgrade} className="bg-red-600 hover:bg-red-700 text-white">
            Upgrade plan
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
