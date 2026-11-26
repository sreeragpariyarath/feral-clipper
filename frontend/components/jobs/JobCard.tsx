import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { ago, streamName } from "@/lib/format";
import type { Job } from "@/lib/types";
import { StatusBadge } from "../ui/Badge";
import { Progress } from "../ui/Progress";

export function JobCard({ job }: { job: Job }) {
  const done = job.steps.filter((s) => s.status === "done").length;
  const running = job.steps.find((s) => s.status === "running");
  return (
    <Link href={`/jobs/${job.id}`} className="group flex items-center gap-4 rounded-xl border bg-card p-4 transition hover:border-primary/40">
      <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-sm font-bold">{job.id}</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-semibold capitalize">{streamName(job.stream_id)}</p>
          <StatusBadge status={job.status} />
          <span className="text-xs text-muted-foreground">{job.kind}</span>
        </div>
        <p className="mt-0.5 truncate text-sm text-muted-foreground">
          {running ? `${running.label} — ${running.message}` : job.error || `${done} of ${job.steps.length} steps · ${ago(job.created_at)}`}
        </p>
        {job.status === "running" && <Progress value={running?.progress ?? null} className="mt-2 h-1.5" />}
      </div>
      <ChevronRight size={18} className="shrink-0 text-muted-foreground transition group-hover:translate-x-0.5" />
    </Link>
  );
}
