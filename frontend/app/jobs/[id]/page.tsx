"use client";

import Link from "next/link";
import { use } from "react";
import { ArrowLeft, Clapperboard } from "lucide-react";
import { FailureBox } from "@/components/jobs/FailureBox";
import { JobActions } from "@/components/jobs/JobActions";
import { LogViewer } from "@/components/jobs/LogViewer";
import { StepTimeline } from "@/components/jobs/StepTimeline";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorNote, Skeleton } from "@/components/ui/States";
import { duration, localTime, streamName } from "@/lib/format";
import { useJob } from "@/lib/queries";

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate text-sm font-medium">{value}</dd>
    </div>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number(use(params).id);
  const { data: job, isLoading, error } = useJob(id);

  if (isLoading) return <Skeleton className="h-96" />;
  if (!job) return <ErrorNote error={error ?? "Job not found"} />;

  const ready = (job.results.ready as { ready?: number } | undefined)?.ready;

  return (
    <>
      <Link href="/jobs" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft size={14} /> Jobs</Link>
      <PageHeader
        title={<span className="flex items-center gap-3 capitalize">Job {job.id}: {streamName(job.stream_id)} <StatusBadge status={job.status} /></span>}
        subtitle={job.source_url || String(job.params.source_path ?? "")}
        actions={
          <>
            {job.status === "done" && (
              <Link href={`/clips?stream=${encodeURIComponent(job.stream_id)}`}>
                <Button variant="primary"><Clapperboard size={16} /> {ready != null ? `${ready} clips ready` : "Open clips"}</Button>
              </Link>
            )}
            <JobActions job={job} />
          </>
        }
      />

      <FailureBox job={job} />

      <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
        <Card>
          <CardHeader title="Steps" subtitle={`${job.steps.filter((s) => s.status === "done").length} of ${job.steps.length} done`} />
          <div className="p-4"><StepTimeline job={job} /></div>
        </Card>
        <Card className="h-fit p-4">
          <dl className="grid gap-3">
            <Fact label="Kind" value={job.kind} />
            <Fact label="Clips asked for" value={String(job.params.top ?? "—")} />
            <Fact label="Created" value={localTime(job.created_at)} />
            <Fact label="Run time" value={duration(job.started_at, job.finished_at) || "—"} />
            <Fact label="Claude tokens" value={`${job.tokens.in.toLocaleString()} in · ${job.tokens.out.toLocaleString()} out`} />
            <Fact label="Stream" value={<Link className="text-primary hover:underline" href={`/clips?stream=${encodeURIComponent(job.stream_id)}`}>{job.stream_id}</Link>} />
          </dl>
        </Card>
      </div>

      <div className="mt-4"><LogViewer lines={job.log ?? []} /></div>
    </>
  );
}
