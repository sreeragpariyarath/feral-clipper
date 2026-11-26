"use client";

import { useState } from "react";
import { Sidebar } from "../../components/layout/Sidebar";
import { NewStreamForm } from "../../components/jobs/NewStreamForm";
import { JobList } from "../../components/jobs/JobList";
import type { Job } from "../../lib/jobs";

/** New stream page: start a download, monitor or render job and watch its progress. */
export default function NewStreamPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [last, setLast] = useState<Job | null>(null);

  function onStarted(job: Job) {
    setLast(job);
    setRefreshKey((k) => k + 1);
  }

  return (
    <div className="flex min-h-screen w-full overflow-x-hidden bg-background text-foreground">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="mx-auto min-w-0 w-full max-w-5xl overflow-x-hidden p-6 md:p-10">
        <header className="mb-6 border-b pb-5">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">New stream</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Paste a Twitch VOD link. Jobs run one at a time; the progress and log show below.
          </p>
        </header>

        <NewStreamForm onStarted={onStarted} />

        {last && (
          <p role="status" className="mt-4 text-sm text-muted-foreground">
            Started job for {last.session} ({last.mode}). Open it in the list below for progress.
          </p>
        )}

        <section aria-label="Jobs" className="mt-8">
          <h2 className="mb-3 text-lg font-semibold">Jobs</h2>
          <JobList refreshKey={refreshKey} />
        </section>
      </main>
    </div>
  );
}
