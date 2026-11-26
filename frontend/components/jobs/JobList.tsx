"use client";

import { useEffect, useState } from "react";
import { getJob, listJobs, type Job } from "../../lib/jobs";

const STATE_STYLE: Record<Job["state"], string> = {
  running: "bg-blue-500/15 text-blue-400",
  done: "bg-green-500/15 text-green-400",
  failed: "bg-red-500/15 text-red-400",
};

/** Lists recent jobs. The newest running job is refreshed every few seconds with its log. */
export function JobList({ refreshKey }: { refreshKey: number }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [detail, setDetail] = useState<Job | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listJobs()
      .then((items) => {
        setJobs(items);
        // open the running job automatically so its progress shows
        const running = items.find((j) => j.state === "running");
        if (running) setOpen((current) => current ?? running.id);
      })
      .catch((e) => setError(e.message));
  }, [refreshKey]);

  // poll the open job while it runs
  useEffect(() => {
    if (!open) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const load = () =>
      getJob(open)
        .then((job) => {
          setDetail(job);
          if (job.state !== "running" && timer) {
            clearInterval(timer);
            listJobs().then(setJobs).catch(() => undefined);
          }
        })
        .catch((e) => setError(e.message));
    load();
    timer = setInterval(load, 4000);
    return () => { if (timer) clearInterval(timer); };
  }, [open]);

  if (error) return <p role="alert" className="text-sm text-red-500">{error}</p>;
  if (!jobs.length) return <p className="text-sm text-muted-foreground">No jobs yet.</p>;

  return (
    <ul className="grid gap-3">
      {jobs.map((job) => (
        <li key={job.id} className="min-w-0 overflow-hidden rounded-xl border bg-card p-4">
          <button type="button" onClick={() => setOpen(open === job.id ? null : job.id)} className="flex w-full items-center justify-between gap-3 text-left">
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold">{job.session || job.url}</span>
              <span className="block text-xs text-muted-foreground">
                {job.mode} · top {job.top} · {job.started}
              </span>
            </span>
            <span className={"shrink-0 rounded-full px-2.5 py-1 text-xs font-medium " + STATE_STYLE[job.state]}>
              {job.state === "running" ? job.step : job.state}
            </span>
          </button>

          {open === job.id && detail && (
            <div className="mt-3">
              {detail.state === "running" && (
                <>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-background">
                    {detail.progress?.percent != null ? (
                      <div className="h-full bg-primary transition-all" style={{ width: `${detail.progress.percent}%` }} />
                    ) : (
                      // no percentage for this step: show a short moving bar instead of a full one
                      <div className="h-full w-1/3 animate-pulse bg-primary/60" />
                    )}
                  </div>
                  <p className="mt-2 break-all text-xs text-muted-foreground">
                    {detail.progress?.percent != null ? `${detail.progress.percent.toFixed(1)}%` : "Working…"}
                    {detail.progress?.eta ? ` · ${detail.progress.eta}` : ""} · {detail.progress?.text}
                  </p>
                </>
              )}
            </div>
          )}

          {open === job.id && detail && (
            <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-background p-3 text-xs text-muted-foreground">
              {(detail.log ?? []).join("\n") || "No log yet."}
            </pre>
          )}
        </li>
      ))}
    </ul>
  );
}
