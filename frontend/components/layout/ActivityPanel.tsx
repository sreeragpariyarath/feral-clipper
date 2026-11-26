"use client";

import Link from "next/link";
import { Activity, PanelRightClose } from "lucide-react";
import { useActivity, useHealth, useJob } from "@/lib/queries";
import { ago } from "@/lib/format";
import type { LiveState } from "@/lib/useLiveEvents";
import { Progress } from "../ui/Progress";
import { cn } from "../ui/cn";

const dot: Record<LiveState, string> = { live: "bg-emerald-500", connecting: "bg-amber-500", offline: "bg-destructive" };

function RunningJob({ id }: { id: number }) {
  const { data: job } = useJob(id);
  if (!job) return null;
  const step = job.steps.find((s) => s.status === "running");
  const done = job.steps.filter((s) => s.status === "done").length;
  return (
    <Link href={`/jobs/${id}`} className="block rounded-xl border bg-card p-3 transition hover:border-primary/40">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Job {id} · {job.kind}</span>
        <span>step {Math.min(done + 1, job.steps.length)} / {job.steps.length}</span>
      </div>
      <p className="mt-1 truncate text-sm font-semibold">{step?.label ?? job.status}</p>
      <Progress value={step?.progress ?? null} className="mt-2" />
      <p className="mt-1.5 truncate text-xs text-muted-foreground">
        {step?.message || "starting"}{step?.eta ? ` · ${step.eta} left` : ""}
      </p>
    </Link>
  );
}

export function ActivityPanel({ live, onClose }: { live: LiveState; onClose: () => void }) {
  const { data: health } = useHealth();
  const { data: events = [] } = useActivity();
  const feed = events.filter((e) => e.kind !== "progress").slice(0, 25);

  return (
    <aside aria-label="Activity" className="sticky top-0 hidden h-dvh w-80 shrink-0 flex-col border-l bg-sidebar xl:flex">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="flex items-center gap-2 font-semibold"><Activity size={16} /> Activity</h2>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={cn("size-2 rounded-full", dot[live])} />{live}
          </span>
          <button onClick={onClose} aria-label="Hide activity" className="rounded p-1 text-muted-foreground hover:bg-muted"><PanelRightClose size={16} /></button>
        </div>
      </div>

      <div className="grid gap-2 border-b p-4">
        {health?.running_job ? <RunningJob id={health.running_job} /> : <p className="text-sm text-muted-foreground">No job running.</p>}
        {!!health?.queued_jobs && <p className="text-xs text-muted-foreground">{health.queued_jobs} more queued</p>}
      </div>

      <ol className="flex-1 overflow-y-auto px-4 py-3 text-sm">
        {feed.map((e) => (
          <li key={e.id} className="border-l-2 py-1.5 pl-3" style={{ borderColor: e.kind === "job" ? "var(--primary)" : undefined }}>
            <p className="leading-snug">{e.message}</p>
            <p className="text-xs text-muted-foreground">{ago(e.created_at)}</p>
          </li>
        ))}
        {!feed.length && <li className="text-muted-foreground">Nothing yet.</li>}
      </ol>
    </aside>
  );
}
