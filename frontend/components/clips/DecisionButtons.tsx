"use client";

import { Check, X } from "lucide-react";
import { usePatchClip } from "@/lib/queries";
import type { Clip, Decision } from "@/lib/types";
import { Button } from "../ui/Button";
import { useToast } from "../ui/Toast";

/** Approve / reject toggles. Clicking the active one sets the clip back to pending. */
export function DecisionButtons({ clip, size = "sm" }: { clip: Clip; size?: "sm" | "md" }) {
  const patch = usePatchClip();
  const toast = useToast();
  const set = (d: Decision) =>
    patch.mutate({ id: clip.id, patch: { decision: clip.decision === d ? "pending" : d } }, { onError: toast.error });

  return (
    <div className="flex gap-1.5">
      <Button size={size} variant={clip.decision === "approved" ? "success" : "outline"} disabled={patch.isPending}
        aria-pressed={clip.decision === "approved"} onClick={() => set("approved")}>
        <Check size={14} /> Approve
      </Button>
      <Button size={size} variant={clip.decision === "rejected" ? "danger" : "outline"} disabled={patch.isPending}
        aria-pressed={clip.decision === "rejected"} onClick={() => set("rejected")}>
        <X size={14} /> Reject
      </Button>
    </div>
  );
}
