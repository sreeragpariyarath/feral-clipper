"use client";

import { RotateCcw, Square } from "lucide-react";
import { useJobAction } from "@/lib/queries";
import type { Job } from "@/lib/types";
import { Button } from "../ui/Button";
import { useToast } from "../ui/Toast";

export function JobActions({ job }: { job: Job }) {
  const cancel = useJobAction("cancel");
  const retry = useJobAction("retry");
  const toast = useToast();

  if (job.status === "queued" || job.status === "running") {
    return (
      <Button variant="danger" loading={cancel.isPending} disabled={job.cancel_requested}
        onClick={() => cancel.mutate(job.id, { onSuccess: () => toast.ok("Stopping the job"), onError: toast.error })}>
        <Square size={14} /> {job.cancel_requested ? "Stopping…" : "Cancel"}
      </Button>
    );
  }
  if (job.status === "cancelled") {                 // failed jobs get Retry in the FailureBox, next to the reason
    return (
      <Button variant="primary" loading={retry.isPending}
        onClick={() => retry.mutate(job.id, { onSuccess: () => toast.ok("Queued again; finished steps are kept"), onError: toast.error })}>
        <RotateCcw size={14} /> Retry
      </Button>
    );
  }
  return null;
}
