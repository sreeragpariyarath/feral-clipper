"use client";

import Link from "next/link";
import { Clapperboard, Coins, HardDrive, ListChecks, Plus } from "lucide-react";
import { ClipCard } from "@/components/clips/ClipCard";
import { StatTile } from "@/components/dashboard/StatTile";
import { JobCard } from "@/components/jobs/JobCard";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/States";
import { useClips, useHealth, useJobs } from "@/lib/queries";

// Haiku-class pricing per million tokens, for a rough spend estimate shown next to the token count.
const USD_PER_M_IN = 1;
const USD_PER_M_OUT = 5;

export default function Dashboard() {
  const { data: health } = useHealth();
  const { data: jobs = [] } = useJobs();
  const { data: clips = [] } = useClips();

  const waiting = clips.filter((c) => c.has_video && c.decision === "pending");
  const approved = clips.filter((c) => c.decision === "approved").length;
  const tokIn = jobs.reduce((n, j) => n + j.tokens.in, 0);
  const tokOut = jobs.reduce((n, j) => n + j.tokens.out, 0);
  const spend = (tokIn * USD_PER_M_IN + tokOut * USD_PER_M_OUT) / 1e6;
  const active = jobs.filter((j) => j.status === "running" || j.status === "queued");

  return (
    <>
      <PageHeader title="Dashboard" subtitle="What's running, and what's waiting for you."
        actions={<Link href="/new"><Button variant="primary"><Plus size={16} /> New job</Button></Link>} />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Waiting for review" value={waiting.length} hint={`${approved} approved so far`} icon={<Clapperboard size={18} />} href="/clips" />
        <StatTile label="Jobs running" value={active.length} hint={health?.running_job ? `job ${health.running_job} now` : "idle"} icon={<ListChecks size={18} />} href="/jobs" />
        <StatTile label="Claude spend (est.)" value={`$${spend.toFixed(2)}`} hint={`${(tokIn + tokOut).toLocaleString()} tokens`} icon={<Coins size={18} />} />
        <StatTile label="Free disk" value={health ? `${health.disk.free_gb} GB` : "—"} hint={health ? `of ${health.disk.total_gb} GB` : ""} icon={<HardDrive size={18} />} href="/streams" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Best clips to review</h2>
            <Link href="/clips" className="text-sm text-primary hover:underline">All clips</Link>
          </div>
          {waiting.length
            ? <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">{[...waiting].sort((a, b) => b.final_score - a.final_score).slice(0, 6).map((c) => <ClipCard key={c.id} clip={c} />)}</div>
            : <EmptyState icon={<Clapperboard />} title="All caught up">No rendered clips are waiting.</EmptyState>}
        </section>
        <Card className="h-fit">
          <CardHeader title="Recent jobs" action={<Link href="/jobs" className="text-sm text-primary hover:underline">All</Link>} />
          <div className="grid gap-2 p-3">
            {jobs.slice(0, 5).map((j) => <JobCard key={j.id} job={j} />)}
            {!jobs.length && <p className="p-2 text-sm text-muted-foreground">No jobs yet.</p>}
          </div>
        </Card>
      </div>
    </>
  );
}
