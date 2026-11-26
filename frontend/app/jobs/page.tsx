"use client";

import Link from "next/link";
import { useState } from "react";
import { ListChecks, Plus } from "lucide-react";
import { JobCard } from "@/components/jobs/JobCard";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { useJobs } from "@/lib/queries";
import { PAGES } from "@/lib/pages";
import { JobListSkeleton } from "@/components/skeletons/cards";

type Filter = "all" | "active" | "done" | "failed";
const match: Record<Filter, (s: string) => boolean> = {
  all: () => true,
  active: (s) => s === "queued" || s === "running",
  done: (s) => s === "done",
  failed: (s) => s === "failed" || s === "cancelled",
};

export default function JobsPage() {
  const { data: jobs, isLoading, error } = useJobs();
  const [filter, setFilter] = useState<Filter>("all");
  const shown = (jobs ?? []).filter((j) => match[filter](j.status));
  const count = (f: Filter) => (jobs ?? []).filter((j) => match[f](j.status)).length;

  return (
    <>
      <PageHeader {...PAGES.jobs}
        actions={<Link href="/new"><Button variant="primary"><Plus size={16} /> New job</Button></Link>} />
      <div className="mb-4">
        <Tabs<Filter> value={filter} onChange={setFilter}
          tabs={(["all", "active", "done", "failed"] as Filter[]).map((f) => ({ value: f, label: f[0].toUpperCase() + f.slice(1), count: count(f) }))} />
      </div>
      <ErrorNote error={error} />
      <div className="grid gap-2">
        {isLoading && <JobListSkeleton count={4} />}
        {shown.map((j) => <JobCard key={j.id} job={j} />)}
        {!isLoading && !shown.length && <EmptyState icon={<ListChecks />} title="No jobs here" />}
      </div>
    </>
  );
}
