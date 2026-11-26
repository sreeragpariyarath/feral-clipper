import { Check, Circle, Loader2, MinusCircle, X } from "lucide-react";
import { duration } from "@/lib/format";
import type { Job, Step } from "@/lib/types";
import { Progress } from "../ui/Progress";
import { cn } from "../ui/cn";

function StepIcon({ status }: { status: Step["status"] }) {
  const base = "grid size-7 shrink-0 place-items-center rounded-full border-2";
  switch (status) {
    case "done": return <span className={cn(base, "border-emerald-500 bg-emerald-500 text-white")}><Check size={14} /></span>;
    case "running": return <span className={cn(base, "border-primary text-primary")}><Loader2 size={14} className="animate-spin" /></span>;
    case "failed": return <span className={cn(base, "border-destructive bg-destructive text-white")}><X size={14} /></span>;
    case "cancelled": case "skipped": return <span className={cn(base, "border-amber-500 text-amber-500")}><MinusCircle size={14} /></span>;
    default: return <span className={cn(base, "border-border text-muted-foreground")}><Circle size={8} /></span>;
  }
}

/** Short line from the step's saved result, e.g. "10 judged, 7 rejected". */
function summary(result: Record<string, unknown> | undefined): string {
  if (!result) return "";
  if (result.skipped) return "already done, reused";
  return Object.entries(result)
    .filter(([k, v]) => typeof v === "number" || (typeof v === "string" && k !== "video" && k !== "audio" && v.length < 30))
    .slice(0, 4)
    .map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`)
    .join(" · ");
}

export function StepTimeline({ job }: { job: Job }) {
  return (
    <ol className="grid">
      {job.steps.map((s, i) => (
        <li key={s.name} className="relative flex gap-3 pb-5 last:pb-0">
          {i < job.steps.length - 1 && (
            <span aria-hidden className={cn("absolute top-7 bottom-0 left-3.5 w-0.5 -translate-x-1/2",
              s.status === "done" ? "bg-emerald-500/60" : "bg-border")} />
          )}
          <StepIcon status={s.status} />
          <div className="min-w-0 flex-1 pt-0.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <p className={cn("font-medium", s.status === "pending" && "text-muted-foreground")}>
                <span className="mr-1.5 text-xs text-muted-foreground">{i + 1}</span>{s.label}
              </p>
              <span className="text-xs tabular-nums text-muted-foreground">
                {s.status === "running" && s.eta ? `${s.eta} left · ` : ""}{duration(s.started_at, s.finished_at)}
              </span>
            </div>
            {s.status === "running" && (
              <div className="mt-2 grid gap-1">
                <Progress value={s.progress} />
                <p className="truncate text-xs text-muted-foreground">
                  {s.progress != null && <span className="mr-2 font-semibold text-foreground tabular-nums">{Math.round(s.progress)}%</span>}
                  {s.message}
                </p>
              </div>
            )}
            {s.status === "done" && <p className="truncate text-xs text-muted-foreground">{summary(job.results[s.name])}</p>}
            {s.status === "failed" && <p className="text-xs text-destructive">{s.message || job.error}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
