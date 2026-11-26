"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useJobAction } from "@/lib/queries";
import type { Job } from "@/lib/types";
import { Button } from "../ui/Button";
import { useToast } from "../ui/Toast";

/** Why the job stopped, what to do, and Retry: it restarts from the failed step, finished steps are kept. */
export function FailureBox({ job }: { job: Job }) {
  const retry = useJobAction("retry");
  const toast = useToast();
  if (job.status !== "failed" || !job.error) return null;
  const failed = job.steps.find((s) => s.status === "failed");
  const kept = job.steps.filter((s) => s.status === "done").length;

  return (
    <div role="alert" className="mb-4 flex flex-wrap items-start gap-4 rounded-xl border border-destructive/40 bg-destructive/5 p-4">
      <AlertTriangle className="mt-0.5 shrink-0 text-destructive" size={20} />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{failed ? `${failed.label} failed` : "The job failed"}</p>
        <p className="mt-1 font-mono text-sm break-words">{job.error}</p>
        {job.error_hint && <p className="mt-2 text-sm">{job.error_hint}</p>}
      </div>
      <Button variant="primary" loading={retry.isPending}
        onClick={() => retry.mutate(job.id, {
          onSuccess: () => toast.ok(`Retrying from ${failed?.label ?? "the failed step"}; ${kept} finished step${kept === 1 ? "" : "s"} kept`),
          onError: toast.error,
        })}>
        <RotateCcw size={14} /> Retry from this step
      </Button>
    </div>
  );
}
